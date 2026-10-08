import { test, expect, type Page } from '@playwright/test';
const backend = process.env.E2E_BACKEND_URL || 'http://127.0.0.1:8000';
async function fillContact(page: Page, suffix: string) {
  await page.getByLabel('Nom et prénom').fill('Vérification E2E');
  await page.getByLabel('Adresse email').fill(`e2e-${suffix}@example.com`);
  await page.getByLabel('Domaine concerné').selectOption('informatique');
  await page.getByLabel('Votre message').fill(`Demande de vérification automatisée E2E ${suffix}.`);
}
async function submitReal(page: Page) {
  const response = page.waitForResponse(r => r.url().endsWith('/api/contact') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Envoyer ma demande' }).click();
  const receipt = await response;
  expect(receipt.status(), JSON.stringify(await receipt.json())).toBe(201);
  await expect(page.getByRole('status')).toContainText('Votre demande est bien enregistrée');
}
test('all published detail pages and local links resolve with semantic headings', async ({page, request}) => {
  const errors: string[]=[]; page.on('pageerror', e => errors.push(e.message));
  const urls=new Set(['/', '/expertises', '/formations', '/a-propos', '/contact', '/mentions-legales', '/confidentialite']);
  for(const [resource,prefix] of [['services','expertises'],['sectors','secteurs'],['courses','formations']]){
    const data=await (await request.get(`${backend}/api/v1/public/${resource}/`)).json();
    for(const item of data) urls.add(`/${prefix}/${item.slug}`);
  }
  const links=new Set<string>();
  for(const url of urls){
    const response=await page.goto(url); expect(response?.status(),url).toBe(200);
    await expect(page.locator('h1'),url).toHaveCount(1);
    expect(await page.title()).toContain('SONUTECH');
    for(const href of await page.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')!))) if(href.startsWith('/')&&!href.startsWith('//'))links.add(href);
    expect(await page.locator('body').evaluate(el=>el.scrollWidth<=innerWidth),url).toBeTruthy();
  }
  for(const url of links) expect((await request.get(url)).status(),url).toBeLessThan(400);
  await page.goto('/page-inexistante-e2e'); await expect(page.locator('main')).toContainText('404');
  expect(errors).toEqual([]);
});
test('mobile menu supports open, Escape, focus restoration, navigation and no overflow',async({page})=>{
  await page.setViewportSize({width:390,height:844}); await page.goto('/');
  const menu=page.getByRole('button',{name:'Ouvrir le menu'});await menu.click();
  await expect(page.getByRole('navigation',{name:'Navigation mobile'})).toBeVisible();
  await page.keyboard.press('Escape');await expect(menu).toBeFocused();
  await menu.click();await page.getByRole('navigation',{name:'Navigation mobile'}).getByRole('link',{name:'Formations'}).click();
  await expect(page).toHaveURL(/\/formations$/);await expect(page.getByRole('navigation',{name:'Navigation mobile'})).toHaveCount(0);
  for(const url of ['/','/contact','/expertises','/formations','/a-propos']) { await page.goto(url);expect(await page.locator('body').evaluate(el=>el.scrollWidth<=innerWidth),url).toBeTruthy(); }
});
test('manual carousel arrows dots and keyboard show every slide',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
  const hero=page.getByRole('region',{name:'Les solutions SONUTECH'});
  const dots=hero.getByRole('button',{name:/Afficher la diapositive/});await expect(dots).toHaveCount(5);
  const initial=await hero.locator('h1').innerText();await hero.getByRole('button',{name:'Diapositive suivante'}).click();await expect(hero.locator('h1')).not.toHaveText(initial,{useInnerText:true});
  await hero.getByRole('button',{name:'Diapositive précédente'}).click();await expect(hero.locator('h1')).toHaveText(initial,{useInnerText:true});
  for(let i=0;i<5;i++){await dots.nth(i).click();await expect(dots.nth(i)).toHaveAttribute('aria-current','true');await expect(hero.locator('h1')).not.toBeEmpty();}
  await hero.focus();await page.keyboard.press('ArrowRight');await expect(dots.nth(0)).toHaveAttribute('aria-current','true');
  await page.keyboard.press('ArrowLeft');await expect(dots.nth(4)).toHaveAttribute('aria-current','true');
});
test('catalogue category and accent-insensitive text filters, empty state and reset',async({page})=>{
  await page.goto('/formations');await expect(page.locator('.course-card')).toHaveCount(4);
  await page.getByRole('button',{name:'CRM',exact:true}).click();await expect(page.locator('.course-card')).toHaveCount(1);
  await expect(page.locator('.course-card')).toContainText('Prendre en main un CRM');
  await page.getByRole('button',{name:'Toutes',exact:true}).click();await page.getByRole('searchbox').fill('numeriques');await expect(page.locator('.course-card')).toHaveCount(1);
  await page.getByRole('searchbox').fill('zzzzzz');await expect(page.getByText('Aucune formation ne correspond')).toBeVisible();
  await page.getByRole('button',{name:'Réinitialiser les filtres'}).click();await expect(page.locator('.course-card')).toHaveCount(4);
});
test('contact stored by real backend with optional fields empty',async({page})=>{await page.goto('/contact?domaine=informatique');await expect(page.getByLabel('Domaine concerné')).toHaveValue('informatique');await fillContact(page,`contact-${Date.now()}`);await submitReal(page);});
test('quote stored by real backend with budget and date',async({page})=>{await page.goto('/contact');await page.getByLabel('Demander un devis').check();await fillContact(page,`quote-${Date.now()}`);await page.getByLabel('Type de projet').fill('Site professionnel');await page.getByLabel('Budget indicatif').selectOption('2 000 à 5 000 €');await page.getByLabel('Échéance souhaitée').fill('2027-03-01');await submitReal(page);});
test('training detail links a real saved inquiry to the selected course',async({page})=>{await page.goto('/formations/crm-relation-client');await page.getByRole('link',{name:'Demander des informations'}).click();await expect(page.getByLabel('Domaine concerné')).toHaveValue('formation');await expect(page.locator('.training-request')).toContainText('Prendre en main un CRM');await fillContact(page,`training-${Date.now()}`);await page.getByLabel('Domaine concerné').selectOption('formation');await submitReal(page);});
test('native required validation prevents request, backend honeypot error is accessible',async({page})=>{
  await page.goto('/contact');let sent=0;page.on('request',r=>{if(r.url().endsWith('/api/contact'))sent++;});
  await page.getByRole('button',{name:'Envoyer ma demande'}).click();expect(sent).toBe(0);await expect(page.locator('input[name="name"]')).toBeFocused();
  await fillContact(page,`validation-${Date.now()}`);await page.locator('input[name="website"]').evaluate((el:HTMLInputElement)=>{el.value='spam.example';});
  const response=page.waitForResponse(r=>r.url().endsWith('/api/contact'));await page.getByRole('button',{name:'Envoyer ma demande'}).click();expect((await response).status()).toBe(400);await expect(page.locator('.form-error[role="alert"]')).toBeVisible();await expect(page.getByText('Votre demande est bien enregistrée.')).toHaveCount(0);
});
test('network failure never reports success and preserves entered values',async({page})=>{await page.goto('/contact');await fillContact(page,'offline');await page.route('**/api/contact',route=>route.abort('failed'));await page.getByRole('button',{name:'Envoyer ma demande'}).click();await expect(page.locator('.form-error[role="alert"]')).toBeVisible();await expect(page.getByLabel('Adresse email')).toHaveValue('e2e-offline@example.com');await expect(page.getByText('Votre demande est bien enregistrée.')).toHaveCount(0);});
test('lost response retry reuses idempotency key and returns original receipt',async({page})=>{
  await page.goto('/contact');await fillContact(page,`replay-${Date.now()}`);
  let firstId='';let firstKey='';let attempts=0;
  await page.route('**/api/contact',async route=>{
    attempts++;
    const data=route.request().postDataJSON();
    const response=await route.fetch();
    const receipt=await response.json();
    if(attempts===1){expect(response.status()).toBe(201);firstId=receipt.id;firstKey=data.idempotency_key;await route.abort('failed');}
    else {expect(response.status()).toBe(200);expect(receipt.id).toBe(firstId);expect(data.idempotency_key).toBe(firstKey);await route.fulfill({response});}
  });
  await page.getByRole('button',{name:'Envoyer ma demande'}).click();
  await expect(page.locator('.form-error[role="alert"]')).toBeVisible();
  await page.getByRole('button',{name:'Envoyer ma demande'}).click();
  await expect(page.getByRole('status')).toContainText('Votre demande est bien enregistrée');
  expect(attempts).toBe(2);
});
