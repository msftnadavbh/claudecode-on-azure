#!/usr/bin/env python3
"""Opt-in, temporary native APIM quota demonstration; always attempt restoration."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET

SUB = "68eab0d1-ab81-4851-b2dd-173dede87582"
TENANT = "16b3c013-d300-468d-ac64-7eda0820b6d3"
OID = "ad4d1fc5-ea1f-4e76-a56c-934f5b1b52e9"
AUD = "api://810dcce2-fcdd-4675-906e-b2aea60afe0e"
CLI_APP = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
RG = f"/subscriptions/{SUB}/resourceGroups/claudepoc-rg/providers/"
SERVICE = RG + "Microsoft.ApiManagement/service/apim-claudecode-project-test-01"
API = SERVICE + "/apis/claude-api"
POLICY = API + "/operations/messages/policies/policy"
MODEL = "claude-opus-5-5"
DEPLOYMENT = RG + "Microsoft.CognitiveServices/accounts/project-test-01/deployments/" + MODEL
GATEWAY = "https://apim-claudecode-project-test-01.azure-api.net/claude/v1/messages"
REFERENCE = Path("/tmp/opencode/claude55-live-private/candidate-policy.xml")
REFERENCE_SHA = "208f0de2beeb25261632e39f554f55e548fbae49357a47fc6e6924bcbb8d33be"
STATE_ROOT = Path.home() / ".local/state/claude-budget-demo"
REMAINING, CONSUMED, MARKER = "x-demo-tokens-remaining", "x-demo-tokens-consumed", "x-budget-demo-run"
RETRY = "x-demo-retry-after"
QUOTA, MIN_INPUT, MAX_INPUT = 1024, 480, 510
PROMPT = "Reply only OK. Synthetic budget test: " + "alpha beta gamma delta " * 47
LABELS = ("synthetic-http-linux-helper", "synthetic-http-windows-helper")


class DemoError(RuntimeError):
    """Only locally authored, credential-free failure codes."""


def require(condition, code):
    if not condition:
        raise DemoError(code)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def structure(xml):
    def node(e):
        return [e.tag, sorted(e.attrib.items()), (e.text or "").strip(),
                (e.tail or "").strip(), [node(child) for child in e]]
    return node(ET.fromstring(xml))


def policy_digest(xml):
    return digest(json.dumps(structure(xml), sort_keys=True))


def normalize(value, envelope=True):
    """Ignore ARM envelope churn, not configuration fields or array ordering."""
    if isinstance(value, list):
        return [normalize(item, envelope) for item in value]
    if not isinstance(value, dict):
        return value
    result = {k: normalize(v, False) for k, v in value.items()
              if not (envelope and k in {"etag", "systemData"})}
    if envelope and isinstance(value.get("value"), list):
        resources = value["value"]
        if all(isinstance(item, dict) and ("id" in item or "name" in item) for item in resources):
            result["value"] = sorted((normalize(item) for item in resources),
                                     key=lambda item: (item.get("id", ""), item.get("name", "")))
    return result


def check_context(current, expected, code):
    changed = sorted(path for path in current.keys() | expected.keys() if current.get(path) != expected.get(path))
    if changed:
        # Paths originate only from locked ARM routes and validated resource names.
        print(json.dumps({"context_drift_paths": changed}), flush=True)
    require(not changed, code)


def candidate(run_id):
    require(str(uuid.UUID(run_id)) == run_id, "invalid_run_id")
    root = ET.fromstring("<policies><inbound><base /></inbound><backend><base /></backend>"
                         "<outbound><base /></outbound><on-error><base /></on-error></policies>")
    ET.SubElement(root.find("inbound"), "llm-token-limit", {
        "counter-key": '@("' + run_id + ':" + ((Jwt)context.Variables["pilotJwt"]).Claims.GetValueOrDefault("tid", "") + ":" + ((Jwt)context.Variables["pilotJwt"]).Claims.GetValueOrDefault("oid", ""))',
        "token-quota": str(QUOTA), "token-quota-period": "Monthly", "estimate-prompt-tokens": "true",
        "retry-after-header-name": RETRY,
        "remaining-quota-tokens-header-name": REMAINING, "tokens-consumed-header-name": CONSUMED,
    })
    header = ET.SubElement(root.find("outbound"), "set-header", {"name": MARKER, "exists-action": "override"})
    ET.SubElement(header, "value").text = run_id
    return ET.tostring(root, encoding="unicode")


def capture(command):
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            timeout=60, check=False)
    require(result.returncode == 0, "token_helper_failed")
    token = result.stdout.strip()
    require(re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token), "invalid_token")
    return token


def token(resource=AUD, windows=False, min_ttl=900):
    if windows:
        value = capture(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                         "& 'C:\\Users\\nadavbh\\AppData\\Local\\claudecodepoc\\desktop-entra-pilot.cmd'; exit $LASTEXITCODE"])
    else:
        value = capture(["az", "account", "get-access-token", "--tenant", TENANT,
                         "--resource", resource, "--query", "accessToken", "--output", "tsv"])
    claims = json.loads(base64.urlsafe_b64decode(value.split(".")[1] + "===").decode())
    # Local checks are not signature verification: the unchanged APIM validator does that.
    require(claims.get("tid") == TENANT and claims.get("oid") == OID
            and claims.get("exp", 0) > time.time() + min_ttl, "token_identity_or_expiry")
    if resource == AUD:
        require(claims.get("aud") == AUD and claims.get("ver") == "1.0"
                and claims.get("appid") == CLI_APP and isinstance(claims.get("roles"), list)
                and "Gateway.Invoke" in claims["roles"]
                and "AiGateway.Invoke" in claims.get("scp", "").split(), "token_claims")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http(method, url, credential, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + credential, "Content-Type": "application/json",
        "Accept": "application/json", **(headers or {})})
    try:
        response = urllib.request.build_opener(NoRedirect()).open(request, timeout=60)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(2_000_001)
        require(len(raw) <= 2_000_000, "response_too_large")
        try:
            body = {} if not raw and response.code == 204 else json.loads(raw)
        except (ValueError, UnicodeError):
            body = None
        if not isinstance(body, dict):
            print(json.dumps({"error": "response_parse_failed", "status": response.code}), flush=True)
            body = {}
        return response.code, {k.lower(): v for k, v in response.headers.items()}, body


def arm(credential, path, method="GET", body=None, headers=None):
    require(path == SERVICE or path.startswith(SERVICE + "/") or path == DEPLOYMENT, "arm_scope")
    require(method == "GET" or (path == POLICY and method in {"PUT", "DELETE"}), "mutation_scope")
    if method == "PUT":
        require(headers == {"If-None-Match": "*"}, "create_only_required")
    if method == "DELETE":
        require(headers and headers.get("If-Match") not in (None, "", "*"), "conditional_delete_required")
    version = "2024-10-01" if path == DEPLOYMENT else "2024-05-01"
    url = "https://management.azure.com" + path + "?api-version=" + version
    if method == "GET" and path.endswith("/policies/policy"):
        url += "&format=rawxml"
    result = http(method, url, credential, body, headers)
    if result[0] >= 400 and result[0] != 404:
        print(json.dumps({"arm_status": result[0], "error_code": safe_error(result[2])[0]}), flush=True)
    return result


def snapshot(credential, expected_policy_digest=None):
    paths = [SERVICE, SERVICE + "/policies/policy", API, API + "/policies/policy",
             API + "/operations", API + "/operations/count-tokens/policies/policy",
             SERVICE + "/backends/foundry-claude", API + "/products", API + "/schemas", DEPLOYMENT]
    values = {}
    for path in paths:
        status, _, body = arm(credential, path)
        optional = path.endswith("/policies/policy") and path != API + "/policies/policy"
        require(status == 200 or (optional and status == 404), "snapshot_http_" + str(status))
        require(not body.get("nextLink"), "snapshot_pagination_unsupported")
        values[path] = body if status == 200 else {"absent": True}
        if path == API + "/products":
            for product in body.get("value", []):
                name = product["name"]
                require(re.fullmatch(r"[A-Za-z0-9_-]+", name), "product_id")
                require(len(body["value"]) <= 20, "too_many_products")
                paths.extend([SERVICE + "/products/" + name, SERVICE + "/products/" + name + "/policies/policy"])
        if path == API + "/schemas":
            for schema in body.get("value", []):
                name = schema["name"]
                require(re.fullmatch(r"[A-Za-z0-9_-]+", name), "schema_id")
                require(len(body["value"]) <= 20, "too_many_schemas")
                paths.append(API + "/schemas/" + name)
    if expected_policy_digest is None:
        reference = REFERENCE.read_text()
        require(digest(reference) == REFERENCE_SHA, "strict_reference_changed")
        expected_policy_digest = policy_digest(reference)
    actual_policy_digest = policy_digest(values[API + "/policies/policy"]["properties"]["value"])
    if actual_policy_digest != expected_policy_digest:
        print(json.dumps({"context_drift_paths": [API + "/policies/policy"]}), flush=True)
    require(actual_policy_digest == expected_policy_digest, "strict_policy_changed")
    require(values[SERVICE]["sku"]["name"] in {"BasicV2", "StandardV2", "PremiumV2"}, "anthropic_requires_v2")
    config = values[API]["properties"]
    require(config["path"] == "claude" and config["subscriptionRequired"] is False
            and config["protocols"] == ["https"], "api_configuration_changed")
    operations = {v["name"]: v["properties"] for v in values[API + "/operations"]["value"]}
    for name, route in (("messages", "/v1/messages"), ("count-tokens", "/v1/messages/count_tokens")):
        require(operations[name]["method"] == "POST" and operations[name]["urlTemplate"] == route, "operation_route_changed")
    require(values[SERVICE + "/backends/foundry-claude"]["properties"]["url"]
            == "https://project-test-01.services.ai.azure.com/anthropic", "backend_changed")
    deployment = values[DEPLOYMENT]
    require(deployment["properties"]["model"] == {"format": "Anthropic", "name": MODEL, "version": "2"}
            and deployment["properties"]["provisioningState"] == "Succeeded"
            and deployment["properties"]["versionUpgradeOption"] == "NoAutoUpgrade"
            and deployment["sku"]["name"] == "GlobalStandard" and deployment["sku"]["capacity"] == 40,
            "model_changed")
    # Retain hashes only: ARM configs can contain credentials; never persist/print them.
    hashes = {path: digest(json.dumps(normalize(value), sort_keys=True)) for path, value in values.items()}
    hashes[API + "/policies/policy"] = actual_policy_digest
    return hashes


def private(path, mode):
    info = path.lstat()
    require(not path.is_symlink() and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == mode, "unsafe_state_permissions")


def save(directory, state):
    temporary = directory / (".state-" + str(uuid.uuid4()))
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(state, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, directory / "state.json")
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def load(directory):
    require(directory.is_absolute() and directory.parent == STATE_ROOT
            and str(uuid.UUID(directory.name)) == directory.name, "state_path")
    private(STATE_ROOT, 0o700)
    private(directory, 0o700)
    private(directory / "state.json", 0o600)
    state = json.loads((directory / "state.json").read_text())
    require(state["target"] == POLICY and state["original_absent"] is True
            and state["candidate"] == candidate(directory.name)
            and state["candidate_sha256"] == digest(state["candidate"])
            and re.fullmatch(r"[0-9a-f]{64}", state["policy_digest"])
            and state["policy_digest"] == state["context"][API + "/policies/policy"], "state_guard")
    return state


def safe_error(body):
    error = body.get("error", body) if isinstance(body, dict) else {}
    error = error if isinstance(error, dict) else {}
    code = error.get("code", error.get("type"))
    quota = isinstance(code, str) and code in {"TokenQuotaExceeded", "token_quota_exceeded"}
    allowed = {"TokenQuotaExceeded", "token_quota_exceeded", "QuotaExceeded", "Unauthorized", "Forbidden",
               "ValidationError", "PermissionDenied", "PreconditionFailed", "AuthorizationFailed"}
    return code if isinstance(code, str) and code in allowed else "unclassified", quota


def dataplane(credential, label, prompt=PROMPT, count=False):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}]}
    if not count:
        body.update(max_tokens=8, stream=False)
    require(len(json.dumps(body).encode()) <= 3000, "request_too_large")
    status, headers, result = http("POST", GATEWAY + ("/count_tokens" if count else ""), credential,
                                   body, {"anthropic-version": "2023-06-01"})
    safe = {k: int(v) for k, v in headers.items() if k in {REMAINING, CONSUMED, RETRY}
            and re.fullmatch(r"-?\d{1,10}" if k == REMAINING else r"\d{1,10}", v)}
    usage = result.get("usage", {})
    usage = usage if isinstance(usage, dict) else {}
    usage = {k: v for k, v in usage.items() if k in {"input_tokens", "output_tokens"}
             and type(v) is int and 0 <= v <= 10000}
    # Recognize native quota errors, never fabricate a 403 or print backend messages.
    safe_code, quota = safe_error(result)
    print(json.dumps({"client": label, "status": status, "headers": safe, "usage": usage,
                      "error_code": safe_code if status >= 400 else None,
                      "error_category": "token_quota" if status == 403 and (quota or RETRY in safe) else None}), flush=True)
    return status, safe, result, headers.get(MARKER)


def restored(directory, state):
    if state.get("phase") == "aborted-before-put":
        print(json.dumps({"aborted_before_put": True, "state": str(directory)}), flush=True)
        return
    # Also covers an accepted PUT whose response/read visibility was delayed.
    time.sleep(30)
    credential = token("https://management.azure.com/", min_ttl=120)
    status, headers, body = arm(credential, POLICY)
    if status != 404:
        require(status == 200 and structure(body["properties"]["value"]) == structure(state["candidate"]), "restore_policy_drift")
        etag = headers.get("etag")
        require(etag and etag != "*" and (not state.get("etag") or state["etag"] == etag), "restore_etag_drift")
        status, _, _ = arm(credential, POLICY, "DELETE", headers={"If-Match": etag})
        require(status in {200, 204}, "restore_delete_http_" + str(status))
    time.sleep(30)
    require(arm(credential, POLICY)[0] == 404, "restore_not_absent")
    check_context(snapshot(credential, expected_policy_digest=state["policy_digest"]), state["context"], "restore_context_drift")
    status, _, _, marker = dataplane(token(min_ttl=120), LABELS[0] + "-restored", prompt="Reply OK.")
    require(status == 200 and marker is None, "restore_canary_failed")
    state["restored"] = True
    save(directory, state)
    print(json.dumps({"restored": True, "state": str(directory)}), flush=True)


def run():
    credential, linux, windows = token("https://management.azure.com/"), token(), token(windows=True)
    context = snapshot(credential)
    require(arm(credential, POLICY)[0] == 404, "operation_policy_present")
    status, _, body, _ = dataplane(linux, LABELS[0] + "-count", count=True)
    require(status == 200 and type(body.get("input_tokens")) is int
             and MIN_INPUT <= body["input_tokens"] <= MAX_INPUT, "count_outside_calibrated_range")
    STATE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    private(STATE_ROOT, 0o700)
    directory = STATE_ROOT / str(uuid.uuid4())
    directory.mkdir(mode=0o700)
    fd = os.open(STATE_ROOT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    xml = candidate(directory.name)
    state = {"target": POLICY, "original_absent": True, "candidate": xml, "candidate_sha256": digest(xml),
             "context": context, "policy_digest": context[API + "/policies/policy"],
             "deadline": int(time.time()) + 600, "restored": False}
    save(directory, state)
    print(json.dumps({"state": str(directory), "deadline": state["deadline"]}), flush=True)
    # Enter finally BEFORE PUT: a timeout can mean Azure accepted the mutation.
    put_attempted = False
    try:
        check_context(snapshot(credential, expected_policy_digest=state["policy_digest"]), context, "pre_put_drift")
        require(arm(credential, POLICY)[0] == 404, "pre_put_drift")
        require(time.time() < state["deadline"], "deadline_exceeded")
        put_attempted = True
        status, _, _ = arm(credential, POLICY, "PUT", {"properties": {"format": "rawxml", "value": xml}},
                           {"If-None-Match": "*"})
        require(status in {200, 201}, "put_http_" + str(status))
        time.sleep(30)
        status, headers, body = arm(credential, POLICY)
        require(status == 200 and structure(body["properties"]["value"]) == structure(xml), "candidate_not_installed")
        require(headers.get("etag") not in (None, "", "*"), "candidate_etag_missing")
        state["etag"] = headers["etag"]
        save(directory, state)
        for index, (client, user_token) in enumerate(zip((LABELS[0], LABELS[1], LABELS[0], LABELS[0]),
                                                       (linux, windows, linux, linux))):
            require(time.time() < state["deadline"], "deadline_exceeded")
            status, safe, body, marker = dataplane(user_token, client)
            if index >= 2 and status == 403:
                require(safe_error(body)[1] or RETRY in safe, "native_token_quota_denial_missing")
                print(json.dumps({"proof": "admission_blocked", "observed_headers": safe,
                                  "same_validated_identity": True}), flush=True)
                break
            usage = body.get("usage", {})
            require(status == 200 and marker == directory.name and REMAINING in safe and CONSUMED in safe,
                    "native_quota_headers_or_success_missing")
            require(isinstance(usage, dict) and type(usage.get("input_tokens")) is int and MIN_INPUT <= usage["input_tokens"] <= MAX_INPUT
                    and type(usage.get("output_tokens")) is int and 0 < usage["output_tokens"] <= 8
                    and not usage.get("cache_read_input_tokens", 0) and not usage.get("cache_creation_input_tokens", 0),
                    "quota_usage_evidence_failed")
        else:
            raise DemoError("native_token_quota_denial_missing")
    finally:
        if not put_attempted:
            state["phase"] = "aborted-before-put"
            try:
                save(directory, state)
            except BaseException:
                print(json.dumps({"state_save_failed": True, "state": str(directory)}), flush=True)
        else:
            try:
                restored(directory, state)
            except BaseException:
                print(json.dumps({"restore_failed": True, "manual_recovery_required": True, "state": str(directory)}), flush=True)
                raise DemoError("restore_failed") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "restore"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--clients-idle", action="store_true", help="all same-user clients stopped for the entire demo")
    parser.add_argument("--state", type=Path)
    args = parser.parse_args(argv)
    if not args.execute or (args.command == "run" and (not args.clients_idle or args.state)) or (args.command == "restore" and not args.state):
        parser.error("--execute required; run also requires --clients-idle; restore requires --state exact-directory")
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    try:
        if args.command == "run":
            run()
        else:
            state = load(args.state)
            restored(args.state, state)
        return 0
    except BaseException as error:
        # Exceptions may contain HTTP bodies, credentials, helper output or config values.
        restore_failed = args.command == "restore" or isinstance(error, DemoError) and str(error) == "restore_failed"
        print(json.dumps({"ok": False, "error": str(error) if isinstance(error, DemoError) else "demo_or_restore_failed",
                          "action": "use_printed_state_for_recovery",
                          "restore_failed": restore_failed, "manual_recovery_required": restore_failed}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
