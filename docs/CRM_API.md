# API CRM PRO

Base `/api/v1/crm/`, session cookies existants, CSRF `X-CSRFToken` obligatoire sur mutations. Auth `/api/v1/auth/csrf/`, `/login/`, `/logout/`, `/me/`. Tous endpoints privés no-store/noindex. Viewer lecture, sales écriture CRM, manager gestion utilisateurs/paramètres. Permissions IA explicites conservées.

`GET bootstrap/`: `{user:{id,username,name,roles,permissions,can_write,can_manage,can_approve,can_configure_ai}, metadata, kpis, dashboard, lookups}`. Metadata clés `prospects.stage`, `opportunities.stage`, etc. valeurs `[{value,label}]`. Lookups leads/clients/projects/opportunities/users tableaux `{id,label}`. KPI prospects,clients,opportunities,projects,revenue,pipeline_amount,conversion_rate,tasks_due. Dashboard pipeline `{stage,label,count,amount}`, services `{name,value}`, recent_projects objets Project.

Collections GET `{count,next,previous,results}`. Pagination `page`, `page_size<=100`, recherche `q`. POST création201, detail GET/PATCH/PUT, DELETE204. Champs FK identifiants ou null; montants chaînes décimales; dates YYYY-MM-DD; timestamps ISO8601. Champs *_name et *_label ajoutés en lecture. Les filtres invalides renvoient400.

- `prospects`: name,email nullable,phone,company,stage,source,tags tableau,owner,next_step,internal_notes. Stages to_qualify/contacted/qualified/proposal/won/not_retained. Sources manual/website/chatbot/referral/other. `POST {id}/convert/` client idempotent. `POST {id}/generate/` brouillon IA pending ou503 si nonconfiguré.
- `clients`: name,company,email,phone,address,status(active/inactive),notes,lead nullable unique.
- `opportunities`: title,lead/client au moins1,stage(new/qualified/proposal/negotiation/won/lost),amount>=0,probability0..100,expected_close,owner,notes.
- `projects`: name,client obligatoire,opportunity,status(planned/in_progress/on_hold/completed),budget,cost>=0,start_date,due_date,description.
- `quotes`: client,project,status(draft/sent/accepted/rejected),issue_date,due_date,notes,items[{description,quantity>0,unit_price>=0,tax_rate0..100}]. number et total_ht/total_tax/total_ttc calculés serveur, numéro DEV-YYYY-NNNNN.
- `invoices`: identique quotes, status(draft/issued/paid/overdue/cancelled), numéro FAC-YYYY-NNNNN. Facture émise : seul status/notes modifiables, pas retourbrouillon. DELETE financier seulementdraft.
- `appointments`: title,lead,start,end,location,notes,status(scheduled/done/cancelled). Filtres `date_from` et `date_to` au format YYYY-MM-DD, bornes incluses dans le fuseau Europe/Paris.
- `tasks`: title,lead,due_date,done bool,priority(low/normal/high),owner.
- `documents`: POST multipart title,file obligatoire<=5MiB,category(contract/quote/invoice/brief/other),lead/client/project optionnels. PDF/PNG/JPG/TXT/CSV/DOCX/XLSX. Lecture original_name,size,download_url. Fichier physique privé `CRM_DOCUMENT_ROOT`, jamais MEDIA_ROOT; téléchargement GET `{id}/download/` authentifié attachment.
- `emails`: lead,subject,body; analysis,status,sent_at,lead_email,recipient_email en lecture. PATCH seulementpending. `POST {id}/reject/`; `POST {id}/send/` permission approve_outreachdraft+SMTP, erreur400 si nonconfiguré,409 déjàtraité. Aucun envoi automatique.
- `users`: manager seulement, username,email,first_name,last_name,is_active,role(viewer/sales/manager),password writeonly requiscréation. PasDELETE. Pasmodification superuser ni propre désactivation/rétrogradation.

`GET/PATCH settings/` objet singleton manager : company_name,email,phone,address,siret,vat_number,currency(EUR).
`GET/PATCH assistant/` permission chatbot.change_assistantconfiguration : enabled,daily_limit,rules,api_key writeonly; lecture configured,model,usage_today,last_test_success,smtp_ready. `POST assistant/test/` test réel budgeté.

## Additions finales
- Opportunities et Projects : service (conseil/digitalisation/ia/formation/energie/autre). Projects : progress entier0..100. Dashboard services = opportunités par activité, uniquement donnéesréelles. KPI prospects = total (pas seulementactifs).
- `inquiries/` GET demandes nonimportées par défaut; `pending=false` toutes. GETdetail, `POST inquiries/{UUID}/import/` crée/réutilise Lead+InquiryImport sans doublon. Formulaire public inchangé.
- Documents max5MiB, stockage privéenv `CRM_DOCUMENT_ROOT`. DELETE supprime fichieraprèscommit.
- Viewer peut seconnecter via ancienformulaire mais endpointslegacyprivés restent restreints; appReact utilise APIRBAC.
- Bootstrap roles APIutilisateurs ne gère jamais les superadministrateurs ni la propre désactivation/rétrogradation.
