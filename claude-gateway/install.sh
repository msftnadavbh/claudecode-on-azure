#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

die() { printf 'Installation refused: %s\n' "$*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo on the NEW POC VM"
[[ $# -eq 1 ]] || die "usage: sudo bash install.sh /root/claude-gateway-input"
for command in python3 openssl realpath stat sha256sum apt-get systemctl runuser useradd install; do
    command -v "$command" >/dev/null || die "missing prerequisite: $command; provision the standard Ubuntu 24.04 tools first"
done
[[ $(uname -m) == x86_64 ]] || die "native Linux x64 is required"
# shellcheck source=/dev/null
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || die "Ubuntu 24.04 is required"

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
[[ $source_dir == /root/* ]] || die "promote the reviewed package to a private directory beneath /root"
[[ $(stat -c '%u:%a' "$source_dir") == 0:700 ]] ||
    die "package directory must be root-owned mode 0700"
for name in install.sh configure.py gateway.template.json claude-gateway.service; do
    [[ -f $source_dir/$name && ! -L $source_dir/$name ]] ||
        die "missing regular package file: $name"
    [[ $(stat -c '%u:%a' "$source_dir/$name") == 0:600 ]] ||
        die "package file $name must be root-owned mode 0600"
done
input=$(realpath -e -- "$1")
[[ $input == /root/* && -d $input && ! -L $1 ]] || die "input must be a root-private directory beneath /root"
[[ $(stat -c '%u:%a' "$input") == 0:700 ]] || die "input directory must be root-owned mode 0700"
[[ ! -e /etc/claude-gateway && ! -e /usr/local/lib/claude-gateway ]] ||
    die "initial installation only; existing installation requires an explicit upgrade/rotation runbook"
for name in settings.json claude tls.crt tls.key ca.crt oidc-secret; do
    [[ -f $input/$name && ! -L $input/$name ]] || die "missing regular input file: $name"
    [[ $(stat -c '%u:%a' "$input/$name") == 0:600 ]] ||
        die "$name must be root-owned mode 0600"
done
python3 "$source_dir/configure.py" "$input/settings.json" --binary "$input/claude" --check-dns >/dev/null
hostname=$(python3 "$source_dir/configure.py" "$input/settings.json" --field hostname)
version=$(python3 "$source_dir/configure.py" "$input/settings.json" --field claude_version)
python3 - "$input/oidc-secret" <<'PY'
from pathlib import Path
import sys
value = Path(sys.argv[1]).read_text().strip()
if len(value) < 16 or any(word in value.lower() for word in ("replace", "changeme", "placeholder")):
    raise SystemExit("Provide the actual OIDC client secret in the root-only oidc-secret file")
PY
openssl x509 -in "$input/tls.crt" -noout -checkend 86400 >/dev/null
openssl verify -CAfile "$input/ca.crt" -untrusted "$input/tls.crt" \
    -purpose sslserver -verify_hostname "$hostname" "$input/tls.crt" >/dev/null
cert_key=$(openssl x509 -in "$input/tls.crt" -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum)
tls_key=$(openssl pkey -in "$input/tls.key" -passin pass: -pubout -outform DER | sha256sum)
[[ $cert_key == "$tls_key" ]] || die "TLS certificate and unencrypted private key do not match"

read -r -p "Type INSTALL-ISOLATED-POC to confirm this VM is disposable and inputs are approved: " confirm
[[ $confirm == INSTALL-ISOLATED-POC ]] || die "confirmation required"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postgresql openssl ca-certificates curl
getent passwd claude-gateway >/dev/null && die "service user already exists"
useradd --system --user-group --home-dir /var/lib/claude-gateway --shell /usr/sbin/nologin claude-gateway
install -d -o root -g claude-gateway -m 0750 /etc/claude-gateway
install -d -o root -g root -m 0755 /usr/local/lib/claude-gateway
install -d -o claude-gateway -g claude-gateway -m 0700 /var/lib/claude-gateway
install -o root -g root -m 0755 "$input/claude" /usr/local/lib/claude-gateway/claude
actual_version=$(runuser -u claude-gateway -- env -i HOME=/var/lib/claude-gateway \
    PATH=/usr/bin:/bin CLAUDE_CONFIG_DIR=/var/lib/claude-gateway DISABLE_UPDATES=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 /usr/local/lib/claude-gateway/claude --version)
[[ $actual_version == "$version (Claude Code)" || $actual_version == "$version" ]] ||
    die "binary version differs from approved pin"
for name in tls.crt tls.key ca.crt oidc-secret; do
    install -o root -g claude-gateway -m 0640 "$input/$name" "/etc/claude-gateway/$name"
done
python3 "$source_dir/configure.py" "$input/settings.json" > /etc/claude-gateway/gateway.yaml
openssl rand -hex 32 > /etc/claude-gateway/session-secret
openssl rand -hex 32 > /etc/claude-gateway/database-secret
install -o root -g root -m 0600 "$input/settings.json" /etc/claude-gateway/install-record.json
chown root:claude-gateway /etc/claude-gateway/{gateway.yaml,session-secret,database-secret}
chmod 0640 /etc/claude-gateway/{gateway.yaml,session-secret,database-secret}

# Own the freshly installed, local-only Ubuntu 24.04 PostgreSQL cluster.
[[ -d /etc/postgresql/16/main ]] || die "expected Ubuntu PostgreSQL 16 main cluster"
printf "listen_addresses = '127.0.0.1'\npassword_encryption = 'scram-sha-256'\n" \
    > /etc/postgresql/16/main/conf.d/claude-gateway.conf
cat > /etc/postgresql/16/main/pg_hba.conf <<'HBA'
local all postgres peer
local all all reject
host claude_gateway claude_gateway 127.0.0.1/32 scram-sha-256
host all all 0.0.0.0/0 reject
host all all ::/0 reject
HBA
chown root:postgres /etc/postgresql/16/main/{conf.d/claude-gateway.conf,pg_hba.conf}
chmod 0640 /etc/postgresql/16/main/{conf.d/claude-gateway.conf,pg_hba.conf}
systemctl enable --now postgresql
systemctl restart postgresql
# Pipe the generated hexadecimal password, never place it in argv or a URL.
{
    printf "SET log_statement = 'none'; SET log_min_duration_statement = -1; SET log_min_error_statement = 'panic';\n"
    printf "CREATE ROLE claude_gateway LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '"
    tr -d '\n' < /etc/claude-gateway/database-secret
    printf "';\nCREATE DATABASE claude_gateway OWNER claude_gateway;\n"
} | runuser -u postgres -- psql -X -q -v ON_ERROR_STOP=1
install -o root -g root -m 0644 "$source_dir/claude-gateway.service" /etc/systemd/system/claude-gateway.service
systemctl daemon-reload
systemctl enable --now claude-gateway
ready=false
for _ in {1..30}; do
    if curl --silent --fail --noproxy '*' --cacert /etc/claude-gateway/ca.crt \
        --resolve "$hostname:8443:127.0.0.1" --max-time 3 \
        "https://$hostname:8443/readyz" >/dev/null; then
        ready=true
        break
    fi
    sleep 2
done
if [[ $ready != true ]]; then
    systemctl disable --now claude-gateway
    die "readiness failed; service stopped. Inspect restricted journal, correct config, then restart; never bypass TLS"
fi
printf 'Gateway ready. Complete browser SSO, denied-user/model and Foundry inference acceptance tests before pilot use.\n'
