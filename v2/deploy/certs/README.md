# Place TLS files here for `docker compose -f docker-compose.prod.yml`:
#
#   fullchain.pem  — certificate + chain (Let's Encrypt or Timeweb)
#   privkey.pem    — private key
#
# Example (certbot on host, then copy):
#   sudo cp /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem ./fullchain.pem
#   sudo cp /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem ./privkey.pem
#   sudo chown "$USER" fullchain.pem privkey.pem
#   chmod 600 privkey.pem
