import { test, expect } from '@playwright/test';

test.use({ baseURL: process.env.CRM_BASE_URL || 'http://127.0.0.1:8500' });
test.skip(process.env.CRM_E2E !== '1', 'Explicit local CRM validation only');

for (const width of [1440, 390]) {
  test(`CRM complete commercial workflow at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    const suffix = `${width}-${Date.now()}`;
    const name = `Claire Martin ${suffix}`;
    const updatedName = `Claire Durand ${suffix}`;
    await page.goto('/crm/prospects/');
    await expect(page).toHaveURL(/connexion/);
    await page.locator('[name=username]').fill(process.env.CRM_USERNAME!);
    await page.locator('[name=password]').fill(process.env.CRM_PASSWORD!);
    await page.getByRole('button', { name: 'Se connecter' }).click();
    await expect(page.getByRole('heading', { name: 'Vos prospects', exact: true })).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Navigation principale' }).getByRole('link')).toHaveCount(3);
    await page.goto('/crm/prospects/nouveau/');
    await page.locator('[name=name]').fill(name);
    await page.locator('[name=phone]').fill('0612345678');
    await page.getByRole('button', { name: 'Enregistrer' }).click();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    const detailURL = page.url();
    await page.goto(`${detailURL}modifier/`);
    await page.locator('[name=name]').fill(updatedName);
    await page.locator('[name=stage]').selectOption('won');
    await page.getByRole('button', { name: 'Enregistrer' }).click();
    await expect(page.getByRole('heading', { name: updatedName, exact: true })).toBeVisible();
    const note = '<script>window.crmXss = true</script> Besoin d’un site vitrine';
    await page.locator('[name=body]').fill(note);
    await page.locator('form').filter({ has: page.locator('[name=body]') }).getByRole('button').click();
    await expect(page.getByText(note, { exact: true })).toBeVisible();
    expect(await page.evaluate(() => 'crmXss' in window)).toBe(false);
    await page.goto(`/crm/prospects/?q=${encodeURIComponent(updatedName)}&stage=won`);
    await expect(page.getByRole('link', { name: updatedName, exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`prospects-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    const leadID = detailURL.split('/').filter(Boolean).at(-1)!;
    await page.goto(`/crm/rendez-vous/nouveau/?lead=${leadID}`);
    await expect(page.locator('[name=lead]')).toHaveValue(leadID);
    await page.locator('[name=title]').fill(`Découverte ${suffix}`);
    await page.locator('[name=start]').fill('2027-03-12T10:00');
    await page.locator('[name=end]').fill('2027-03-12T09:00');
    await page.getByRole('button', { name: 'Enregistrer' }).click();
    await expect(page.getByText('La fin doit être après le début.')).toBeVisible();
    await page.locator('[name=end]').fill('2027-03-12T11:00');
    await page.getByRole('button', { name: 'Enregistrer' }).click();
    const appointment = page.locator('article').filter({ hasText: `Découverte ${suffix}` });
    await expect(appointment).toContainText('10:00');
    if (width < 500) {
      const contentBox = await appointment.locator('.row-content').boundingBox();
      expect(contentBox?.width).toBeGreaterThan(170);
    }
    await appointment.getByRole('link', { name: /Modifier/ }).click();
    await expect(page.locator('[name=start]')).toHaveValue('2027-03-12T10:00');
    await page.locator('[name=status]').selectOption('done');
    await page.getByRole('button', { name: 'Enregistrer' }).click();
    await page.goto('/crm/rendez-vous/?filter=all');
    await expect(page.locator('article').filter({ hasText: `Découverte ${suffix}` })).toContainText('Terminé');
    await page.screenshot({ path: testInfo.outputPath(`appointments-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    await page.goto(`/crm/a-faire/nouveau/?lead=${leadID}`);
    await page.locator('[name=title]').fill(`Envoyer le devis ${suffix}`);
    await page.locator('[name=due_date]').fill('2027-03-15');
    await page.getByRole('button', { name: 'Enregistrer' }).click();
    let task = page.locator('article').filter({ hasText: `Envoyer le devis ${suffix}` });
    await task.getByRole('link', { name: /Modifier/ }).click();
    await page.locator('[name=title]').fill(`Relancer le devis ${suffix}`);
    await page.getByRole('button', { name: 'Enregistrer' }).click();
    task = page.locator('article').filter({ hasText: `Relancer le devis ${suffix}` });
    await task.getByRole('button', { name: /Terminer/ }).click();
    await page.goto('/crm/a-faire/?filter=done');
    await expect(task).toContainText('Terminée');
    await task.getByRole('button', { name: 'Remettre à faire' }).click();
    await expect(task).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`tasks-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const response = await page.goto('/crm/prospects/');
    expect(response?.headers()['cache-control']).toContain('no-store');
    expect(response?.headers()['x-robots-tag']).toContain('noindex');
    await page.getByRole('button', { name: 'Déconnexion' }).click();
    await page.goto('/crm/prospects/');
    await expect(page).toHaveURL(/connexion/);
    expect(errors).toEqual([]);
  });
}
