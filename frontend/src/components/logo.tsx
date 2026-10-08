import Image from 'next/image';
export function Logo({ watermark = false }: { watermark?: boolean }) {
  return <span className={`logo ${watermark ? 'watermark' : ''}`}><Image src="/images/logo.svg" width={59} height={48} alt="" priority={!watermark} /><span>SONUTECH</span></span>;
}
