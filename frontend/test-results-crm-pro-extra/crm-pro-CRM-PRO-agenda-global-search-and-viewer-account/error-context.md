# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: crm-pro.spec.ts >> CRM PRO agenda, global search and viewer account
- Location: tests/crm-pro.spec.ts:147:5

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: getByRole('status')
Expected substring: "Utilisateur enregistré"
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toContainText" getByRole('status') with timeout 5000ms
  - waiting for getByRole('status')

```

```yaml
- alert: Votre activité, en toute simplicité.
- link "Aller au contenu":
  - /url: "#crm-content"
- complementary:
  - link "SONUTECH CRM PRO":
    - /url: /crm
  - text: ESPACE DE TRAVAIL
  - navigation "Menu CRM":
    - link "Tableau de bord":
      - /url: /crm
    - link "Prospects":
      - /url: /crm/prospects
    - link "Clients":
      - /url: /crm/clients
    - link "Opportunités":
      - /url: /crm/opportunites
    - link "Projets":
      - /url: /crm/projets
    - link "Devis & Factures":
      - /url: /crm/devis-factures
    - link "Agenda":
      - /url: /crm/agenda
    - link "Emails":
      - /url: /crm/emails
    - link "Documents":
      - /url: /crm/documents
    - link "Assistant IA IA":
      - /url: /crm/assistant-ia
  - link "Paramètres":
    - /url: /crm/parametres
  - text: Espace privé SONUTECH
- banner:
  - text: CRM
  - strong: Paramètres
  - search:
    - textbox "Rechercher un prospect, client ou projet":
      - /placeholder: Rechercher client, projet…
  - text: CR
  - strong: crm-validation@example.com
  - text: Administrateur
  - button "Se déconnecter"
- main:
  - heading "Paramètres" [level=1]
  - paragraph: Votre espace commercial, connecté à votre équipe.
  - heading "Informations de l’entreprise" [level=2]
  - paragraph: Connecté en tant que crm-validation@example.com · Horaires Europe/Paris.
  - alert: "password : Le mot de passe est trop semblable au champ « nom d’utilisateur »."
  - text: Nom de l’entreprise
  - textbox "Nom de l’entreprise": SONUTECH
  - text: Email
  - textbox "Email": sonutech@sonutech.fr
  - text: Téléphone
  - textbox "Téléphone": 07 75 78 78 25
  - text: SIRET
  - textbox "SIRET"
  - text: Numéro de TVA
  - textbox "Numéro de TVA"
  - text: Adresse
  - textbox "Adresse"
  - paragraph: "Devise des devis et factures : euro (EUR)."
  - button "Enregistrer"
  - heading "Votre équipe" [level=2]
  - button "Ajouter"
  - button "crm-activation-validation@example.test Commercial · Actif":
    - strong: crm-activation-validation@example.test
    - text: Commercial · Actif
  - button "crm-validation@example.com Responsable · Actif":
    - strong: crm-validation@example.com
    - text: Responsable · Actif
  - heading "Nouvel utilisateur" [level=3]
  - button "Annuler la modification"
  - text: Identifiant
  - textbox "Identifiant": lecture-1791434141406
  - text: Prénom
  - textbox "Prénom": Alice
  - text: Nom
  - textbox "Nom"
  - text: Email
  - textbox "Email"
  - text: Mot de passe
  - textbox "Mot de passe": Local-only-Viewer-1791434141406!
  - text: Rôle
  - combobox "Rôle":
    - option "Lecture seule" [selected]
    - option "Commercial"
    - option "Responsable"
  - checkbox "Compte actif" [checked]
  - text: Compte actif
  - button "Enregistrer l’utilisateur"
- contentinfo:
  - text: © 2026 SONUTECH. Tous droits réservés. Espace privé
  - link "Aide":
    - /url: /contact
  - link "Confidentialité":
    - /url: /confidentialite
```

# Test source

```ts
  102 |   expect(response.status()).toBe(200);
  103 |   expect(response.headers()['content-disposition']).toContain('attachment');
  104 |   expect(await response.text()).toContain('Dossier de validation privé');
  105 |   const anonymous = await browser.newContext();
  106 |   expect((await anonymous.request.get(new URL(download!,page.url()).href)).status()).toBe(403);
  107 |   await anonymous.close();
  108 |   await dialog.getByRole('button', { name:'Fermer la fiche' }).click();
  109 |   await menu.getByRole('link', { name:'Emails', exact:true }).click();
  110 |   await page.getByRole('button', { name:'Ajouter un brouillon' }).click();
  111 |   dialog = page.getByRole('dialog');
  112 |   await dialog.getByRole('combobox', { name:/^Prospect/ }).selectOption({ label:name });
  113 |   await dialog.getByLabel(/^Objet/).fill(`Votre projet ${suffix}`);
  114 |   await dialog.getByLabel(/^Message/).fill('Bonjour, précisons votre besoin avant de préparer un devis.');
  115 |   await dialog.getByRole('button', { name:'Enregistrer', exact:true }).click();
  116 |   await expect(dialog).not.toBeVisible();
  117 |   await page.getByRole('button', { name:`Votre projet ${suffix}`, exact:true }).click();
  118 |   await expect(page.getByRole('dialog')).toContainText(`claire-${suffix}@example.test`);
  119 |   await page.getByRole('dialog').getByRole('button', { name:'Fermer la fiche' }).click();
  120 |   await page.screenshot({ path:info.outputPath('emails-desktop.png') });
  121 |   expect(errors).toEqual([]);
  122 | });
  123 | 
  124 | test('CRM PRO mobile drawer and center-only scroll', async ({ page }, info) => {
  125 |   page.setDefaultTimeout(15000);
  126 |   await page.setViewportSize({ width:390,height:844 });
  127 |   await page.goto('/crm');
  128 |   await page.getByLabel('Identifiant', { exact:true }).fill(process.env.CRM_USERNAME!);
  129 |   await page.getByLabel('Mot de passe', { exact:true }).fill(process.env.CRM_PASSWORD!);
  130 |   await page.getByRole('button', { name:'Se connecter', exact:true }).click();
  131 |   await expect(page.getByRole('heading', { name:'Tableau de bord', exact:true })).toBeVisible();
  132 |   expect(await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth && document.documentElement.scrollHeight<=innerHeight)).toBe(true);
  133 |   await page.screenshot({ path:info.outputPath('dashboard-mobile.png') });
  134 |   await page.getByRole('button', { name:'Ouvrir le menu', exact:true }).click();
  135 |   const menu = page.getByRole('navigation', { name:'Menu CRM' });
  136 |   await expect(menu).toBeVisible();
  137 |   await menu.getByRole('link', { name:'Prospects', exact:true }).click();
  138 |   await expect(page.getByRole('heading', { name:'Prospects', exact:true })).toBeVisible();
  139 |   await page.getByRole('button', { name:'Ajouter un prospect' }).click();
  140 |   await expect(page.getByRole('dialog')).toBeVisible();
  141 |   await page.keyboard.press('Escape');
  142 |   await expect(page.getByRole('dialog')).not.toBeVisible();
  143 |   await page.screenshot({ path:info.outputPath('prospects-mobile.png') });
  144 |   expect(await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth && document.documentElement.scrollHeight<=innerHeight)).toBe(true);
  145 | });
  146 | 
  147 | test('CRM PRO agenda, global search and viewer account', async ({ page }, info) => {
  148 |   page.setDefaultTimeout(15000);
  149 |   await page.setViewportSize({width:1536,height:1024});
  150 |   await page.goto('/crm');
  151 |   await page.getByLabel('Identifiant', {exact:true}).fill(process.env.CRM_USERNAME!);
  152 |   await page.getByLabel('Mot de passe', {exact:true}).fill(process.env.CRM_PASSWORD!);
  153 |   await page.getByRole('button', {name:'Se connecter',exact:true}).click();
  154 |   const menu=page.getByRole('navigation',{name:'Menu CRM'});
  155 |   await expect(menu).toBeVisible();
  156 |   const search=page.getByLabel('Rechercher un prospect, client ou projet');
  157 |   await search.fill('Réalisation');
  158 |   await search.press('Enter');
  159 |   const projectResult=page.locator('button').filter({has:page.locator('span').getByText('projet',{exact:true})}).first();
  160 |   await projectResult.click();
  161 |   await expect(page.getByRole('dialog').getByRole('heading',{name:'Modifier projet'})).toBeVisible();
  162 |   await page.getByRole('button',{name:'Fermer la fiche'}).click();
  163 |   await search.fill('Claire Martin');
  164 |   const clientResult=page.locator('button').filter({has:page.locator('span').getByText('client',{exact:true})}).first();
  165 |   await clientResult.click();
  166 |   await expect(page.getByRole('dialog').getByRole('heading',{name:'Modifier client'})).toBeVisible();
  167 |   await page.getByRole('button',{name:'Fermer la fiche'}).click();
  168 |   await menu.getByRole('link',{name:'Agenda',exact:true}).click();
  169 |   const todayButton=page.getByRole('button',{name:'Aujourd’hui',exact:true});
  170 |   await expect(todayButton).toBeDisabled();
  171 |   await page.getByRole('button',{name:'Semaine suivante'}).click();
  172 |   await expect(todayButton).toBeEnabled();
  173 |   await todayButton.click();
  174 |   await expect(todayButton).toBeDisabled();
  175 |   await page.getByRole('button',{name:'Ajouter un rendez-vous'}).click();
  176 |   const dialog=page.getByRole('dialog');
  177 |   const title=`Appel de découverte ${Date.now()}`;
  178 |   const today=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});
  179 |   await dialog.getByLabel(/^Objet/).fill(title);
  180 |   await dialog.getByLabel(/^Début/).fill(`${today}T10:00`);
  181 |   await dialog.getByLabel(/^Fin/).fill(`${today}T11:00`);
  182 |   await dialog.getByRole('button',{name:'Enregistrer',exact:true}).click();
  183 |   await expect(dialog).not.toBeVisible();
  184 |   const event=page.getByRole('button').filter({has:page.locator('time')}).filter({hasText:title});
  185 |   await expect(event).toContainText('10:00');
  186 |   await event.click();
  187 |   await expect(dialog.getByLabel(/^Début/)).toHaveValue(`${today}T10:00`);
  188 |   await dialog.getByLabel(/^Objet/).fill(`${title} modifié`);
  189 |   await dialog.getByRole('button',{name:'Enregistrer',exact:true}).click();
  190 |   await expect(event).toContainText('modifié');
  191 |   await page.screenshot({path:info.outputPath('agenda-desktop.png')});
  192 |   await page.getByRole('link',{name:'Paramètres',exact:true}).click();
  193 |   await page.getByRole('button',{name:'Ajouter',exact:true}).click();
  194 |   const memberForm=page.locator('form').filter({has:page.getByRole('button',{name:'Enregistrer l’utilisateur'})});
  195 |   const username=`lecture-${Date.now()}`;
  196 |   const password=`Local-only-Viewer-${Date.now()}!`;
  197 |   await memberForm.getByLabel('Identifiant',{exact:true}).fill(username);
  198 |   await memberForm.getByLabel('Prénom',{exact:true}).fill('Alice');
  199 |   await memberForm.getByLabel('Mot de passe',{exact:true}).fill(password);
  200 |   await memberForm.getByRole('combobox',{name:/^Rôle/}).selectOption('viewer');
  201 |   await memberForm.getByRole('button',{name:'Enregistrer l’utilisateur'}).click();
> 202 |   await expect(page.getByRole('status')).toContainText('Utilisateur enregistré');
      |                                          ^ Error: expect(locator).toContainText(expected) failed
  203 |   await page.getByRole('button',{name:'Se déconnecter'}).click();
  204 |   await page.getByLabel('Identifiant',{exact:true}).fill(username);
  205 |   await page.getByLabel('Mot de passe',{exact:true}).fill(password);
  206 |   await page.getByRole('button',{name:'Se connecter',exact:true}).click();
  207 |   await menu.getByRole('link',{name:'Prospects',exact:true}).click();
  208 |   await expect(page.getByRole('heading',{name:'Prospects',exact:true})).toBeVisible();
  209 |   await expect(page.getByRole('button',{name:'Ajouter un prospect'})).toHaveCount(0);
  210 |   await page.getByRole('link',{name:'Paramètres',exact:true}).click();
  211 |   await expect(page.getByText('Les paramètres sont réservés aux responsables.')).toBeVisible();
  212 | });
  213 | 
```