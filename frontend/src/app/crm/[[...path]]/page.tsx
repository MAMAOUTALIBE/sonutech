import type { Metadata } from 'next';
import { CrmApp } from '@/components/crm/crm-app';
export const metadata:Metadata={title:'CRM PRO',robots:{index:false,follow:false}};
export default function CrmPage(){return <CrmApp/>;}
