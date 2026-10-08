import { test, expect } from '@playwright/test';

test.skip(process.env.CHATBOT_E2E !== '1', 'Explicit isolated chatbot validation only');

for (const width of [1440, 390]) {
  test(`mocked chatbot consent, retry and contact at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    let startCalls = 0;
    let messageCalls = 0;
    let contactCalls = 0;
    let firstMessageId = '';
    await page.route('**/api/chat', async route => {
      const data = route.request().postDataJSON();
      if (data.action === 'start') {
        startCalls++;
        return route.fulfill({ json: { available: true, token: 'isolated-browser-token', reply: 'Bonjour, quel est votre projet ?' } });
      }
      if (data.action === 'message') {
        messageCalls++;
        if (messageCalls === 1) {
          firstMessageId = data.message_id;
          return route.abort('failed');
        }
        expect(data.message_id).toBe(firstMessageId);
        return route.fulfill({ json: { available: true, reply: '<script>window.chatXss=true</script> Nous pouvons étudier votre site.', suggest_contact: true } });
      }
      expect(data.action).toBe('contact');
      expect(data.consent).toBe(true);
      expect(data.email).toBe('claire@example.test');
      expect(data.contact_id).toMatch(/^[a-f0-9-]{36}$/);
      contactCalls++;
      return route.fulfill({ json: { captured: true, detail: 'Demande enregistrée.' } });
    });
    await page.goto('/');
    const launcher = page.getByRole('button', { name: /Parlons de votre projet/ });
    await launcher.click();
    const dialog = page.getByRole('dialog', { name: 'Assistant IA SONUTECH' });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Groq');
    expect(startCalls).toBe(0);
    await page.keyboard.press('Escape');
    await expect(launcher).toBeFocused();
    await launcher.click();
    await dialog.getByRole('button', { name: 'Accepter et discuter' }).click();
    await expect(dialog.getByRole('log')).toContainText('Bonjour, quel est votre projet ?');
    await dialog.getByLabel('Votre message', { exact: true }).fill('Je souhaite un site vitrine.');
    await dialog.getByRole('button', { name: 'Envoyer le message' }).click();
    await expect(dialog.getByRole('alert')).toBeVisible();
    await dialog.getByRole('button', { name: 'Réessayer ce message' }).click();
    await expect(dialog.getByRole('log')).toContainText('Nous pouvons étudier votre site.');
    expect(messageCalls).toBe(2);
    expect(await page.evaluate(() => 'chatXss' in window)).toBe(false);
    await page.screenshot({ path: testInfo.outputPath(`chat-${width}.png`), fullPage: true });
    const box = await dialog.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    await dialog.getByRole('button', { name: 'Être recontacté', exact: true }).click();
    await dialog.getByLabel('Votre nom').fill('Claire Martin');
    await dialog.getByLabel('Email', { exact: true }).fill('claire@example.test');
    await dialog.getByLabel('Votre demande').fill('Un site vitrine pour mon activité.');
    await dialog.getByRole('button', { name: 'Transmettre ma demande' }).click();
    expect(contactCalls).toBe(0);
    await dialog.getByRole('checkbox').check();
    await page.screenshot({ path: testInfo.outputPath(`chat-contact-${width}.png`), fullPage: true });
    await dialog.getByRole('button', { name: 'Transmettre ma demande' }).click();
    await expect(dialog.getByRole('status')).toContainText('Votre demande a été transmise');
    await expect(dialog).toContainText('aucun créneau n’est réservé automatiquement');
    expect(contactCalls).toBe(1);
    await dialog.getByRole('button', { name: 'Nouvelle discussion' }).click();
    await expect(dialog.getByRole('button', { name: 'Accepter et discuter' })).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test('mocked unavailable provider and expired session report honest errors', async ({ page }) => {
  let state = 'unavailable';
  await page.route('**/api/chat', route => {
    if (state === 'unavailable') return route.fulfill({ status: 503, json: { detail: 'Assistant temporairement indisponible.' } });
    if (route.request().postDataJSON().action === 'start') return route.fulfill({ json: { available: true, token: 'isolated-browser-token', reply: 'Bonjour.' } });
    return route.fulfill({ status: 401, json: { detail: 'Votre conversation a expiré.' } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: /Parlons de votre projet/ }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Accepter et discuter' }).click();
  await expect(dialog.getByRole('alert')).toContainText('indisponible');
  await expect(dialog.getByRole('log')).toHaveCount(0);
  state = 'available';
  await dialog.getByRole('button', { name: 'Accepter et discuter' }).click();
  await dialog.getByLabel('Votre message', { exact: true }).fill('Bonjour');
  await dialog.getByRole('button', { name: 'Envoyer le message' }).click();
  await expect(dialog.getByRole('alert')).toContainText('expiré');
  await expect(dialog.getByLabel('Votre message', { exact: true })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Recommencer la discussion' }).click();
  await expect(dialog.getByRole('button', { name: 'Accepter et discuter' })).toBeVisible();
});
