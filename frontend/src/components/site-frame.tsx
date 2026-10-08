'use client';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
export function SiteFrame({children,header,footer,chat}:{children:ReactNode;header:ReactNode;footer:ReactNode;chat:ReactNode}) {
  const path=usePathname();
  if(path==='/crm'||path.startsWith('/crm/')) return <>{children}</>;
  return <><a href="#contenu" className="skip-link">Aller au contenu</a>{header}<main id="contenu">{children}</main>{footer}{chat}</>;
}
