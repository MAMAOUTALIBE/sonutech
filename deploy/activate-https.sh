#!/bin/sh
set -eu

# Run as root on the SONUTECH VPS after updating the domain's DNS records.
expected_ip=195.35.25.236
for domain in sonutech.fr www.sonutech.fr; do
    resolved=$(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u)
    if [ "$resolved" != "$expected_ip" ]; then
        printf '%s must resolve exclusively to %s before HTTPS activation.\n' "$domain" "$expected_ip" >&2
        exit 1
    fi
done

certbot certonly --non-interactive --webroot -w /var/www/letsencrypt \
    --cert-name sonutech.fr -d sonutech.fr -d www.sonutech.fr
cp /etc/nginx/sites-available/sonutech.fr /opt/sonutech/sonutech-nginx.previous
install -m 644 /opt/sonutech/deploy/sonutech-https.conf /etc/nginx/sites-available/sonutech.fr
if ! nginx -t; then
    cp /opt/sonutech/sonutech-nginx.previous /etc/nginx/sites-available/sonutech.fr
    exit 1
fi
systemctl reload nginx
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nnginx -t && systemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/sonutech-nginx-reload
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/sonutech-nginx-reload
curl --fail --silent --show-error --retry 5 --retry-all-errors --retry-delay 1 --output /dev/null https://sonutech.fr/
printf 'SONUTECH is available at https://sonutech.fr\n'
