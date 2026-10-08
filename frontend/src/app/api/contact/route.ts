import { NextRequest, NextResponse } from 'next/server';
import { isIP } from 'node:net';
export async function POST(request:NextRequest){
  // Only relay to the single public submission endpoint; never proxy management APIs.
  const origin=request.headers.get('origin');
  const allowed=new Set([request.nextUrl.origin,process.env.SITE_URL||process.env.NEXT_PUBLIC_SITE_URL||'http://localhost:3000']);
  if(process.env.NODE_ENV==='development'){allowed.add('http://127.0.0.1:3000');allowed.add('http://localhost:3000');}
  if(origin&&!allowed.has(origin))return NextResponse.json({detail:'Origine non autorisée.'},{status:403});
  if(Number(request.headers.get('content-length')||0)>32000)return NextResponse.json({detail:'Demande trop volumineuse.'},{status:413});
  try{
    const body=await request.text();if(new TextEncoder().encode(body).length>32000)return NextResponse.json({detail:'Demande trop volumineuse.'},{status:413});
    JSON.parse(body);
    const relayHeaders:Record<string,string>={'Content-Type':'application/json'};
    const clientIp=request.headers.get('x-real-ip')||'';
    const proxySecret=process.env.PROXY_SHARED_SECRET||'';
    // Enable only behind an ingress which overwrites X-Real-IP, with the app port private.
    if(process.env.TRUST_PROXY_HEADERS==='1' && proxySecret.length>=32 && isIP(clientIp)){
      relayHeaders['X-Sonutech-Proxy-Secret']=proxySecret;
      relayHeaders['X-Sonutech-Client-IP']=clientIp;
    }
    const response=await fetch(`${process.env.BACKEND_URL||'http://127.0.0.1:8000'}/api/v1/public/inquiries/`,{method:'POST',headers:relayHeaders,body,signal:AbortSignal.timeout(20000),cache:'no-store'});
    const result=await response.json();
    return NextResponse.json(result,{status:response.status,headers:{'Cache-Control':'no-store',...(response.headers.get('retry-after')?{'Retry-After':response.headers.get('retry-after')!}:{})}});
  }catch(error){return NextResponse.json({detail:error instanceof SyntaxError?'Contenu JSON invalide.':'Service temporairement indisponible. Réessayez votre demande.'},{status:error instanceof SyntaxError?400:503});}
}
