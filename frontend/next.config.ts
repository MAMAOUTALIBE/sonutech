import type { NextConfig } from 'next';
const nextConfig: NextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  devIndicators: false,
  images: { localPatterns: [{ pathname: '/images/**' }, { pathname: '/media/**' }] },
  async rewrites() {
    return [{source:'/api/v1/:path*',destination:`${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/v1/:path*/`}];
  },
  async headers() {
    return [{source:'/crm/:path*',headers:[{key:'X-Robots-Tag',value:'noindex, nofollow'},{key:'Cache-Control',value:'private, no-store'}]},{source:'/:path*',headers:[{key:'X-Content-Type-Options',value:'nosniff'},{key:'Referrer-Policy',value:'strict-origin-when-cross-origin'},{key:'X-Frame-Options',value:'DENY'},{key:'Permissions-Policy',value:'camera=(), microphone=(), geolocation=()'}]}];
  },
};
export default nextConfig;
