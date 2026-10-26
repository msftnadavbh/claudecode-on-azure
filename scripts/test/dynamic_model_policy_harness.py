"""Compile the actual XML-decoded expressions, without downloads or a NuGet restore.

Uses an installed .NET SDK and its Newtonsoft.Json.dll, or explicit CSC and
NEWTONSOFT_JSON paths. WSL/native csc builds also require POLICY_TEST_BUILD_ROOT
on a Windows volume and PowerShell (no profile); only owned temporary files change.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET


def checked(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=90, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{command[0]} exited {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def generate_expressions(policies):
    expressions = {}

    def visit(node):
        if node.tag == "trace":
            return  # Existing diagnostic interpolation is unrelated and uses C# 6.
        for value in [*node.attrib.values(), (node.text or "").strip()]:
            if value.startswith(("@(", "@{")):
                expressions.setdefault(value, len(expressions))
        for child in node:
            visit(child)

    for policy in policies.values():
        visit(ET.fromstring(policy))
    methods = []
    for expression, index in expressions.items():
        body = expression[2:-1] if expression.startswith("@{") else "return " + expression[2:-1] + ";"
        methods.append(f"static object Expression{index}(SyntheticContext context) {{ {body} }}")
    entries = ",\n".join("{ " + json.dumps(expression) + f", Expression{index} }}" for expression, index in expressions.items())
    policy_entries = ",\n".join("{ " + json.dumps(name) + ", XElement.Parse(" + json.dumps(xml) + ") }" for name, xml in policies.items())
    return '''using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Xml.Linq;
using Newtonsoft.Json.Linq;
public static class PolicyExpressions {
public static readonly Dictionary<string, XElement> Policies = new Dictionary<string, XElement> {
''' + policy_entries + '''
};
static readonly Dictionary<string, Func<SyntheticContext, object>> Expressions = new Dictionary<string, Func<SyntheticContext, object>> {
''' + entries + '''
};
public static object Evaluate(string text, SyntheticContext context) {
    Func<SyntheticContext, object> expression;
    if (Expressions.TryGetValue(text, out expression)) { return expression(context); }
    if (text.StartsWith("@")) { throw new Exception("Uncompiled expression"); }
    return text;
}
''' + "\n".join(methods) + "\n}\n"


class CompiledPolicy:
    def __init__(self, policies):
        csc = os.environ.get("CSC")
        self.windows = bool(csc)
        build_root = os.environ.get("POLICY_TEST_BUILD_ROOT") if csc else None
        if csc and not build_root:
            raise RuntimeError("Explicit CSC requires POLICY_TEST_BUILD_ROOT on the Windows test volume")
        self.temporary = tempfile.TemporaryDirectory(prefix="opencode-pr6-" if csc else "pr6-policy-", dir=build_root)
        self.directory = Path(self.temporary.name)
        self.environment = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.directory),
                            "TMPDIR": str(self.directory), "DOTNET_CLI_HOME": str(self.directory),
                            "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
                            "DOTNET_NOLOGO": "1", "DOTNET_EnableDiagnostics": "0",
                            "NUGET_PACKAGES": str(self.directory / "packages")}
        try:
            source = self.directory / "PolicyExpressions.cs"
            source.write_text(generate_expressions(policies), encoding="utf-8")
            harness = self.directory / "Harness.cs"
            shutil.copyfile(Path(__file__).with_suffix(".cs"), harness)
            if csc:
                if not os.environ.get("NEWTONSOFT_JSON"):
                    raise RuntimeError("Explicit CSC requires NEWTONSOFT_JSON; no packages will be installed")
                compiler = Path(csc)
                assembly = Path(os.environ["NEWTONSOFT_JSON"])
                self.powershell = shutil.which("powershell.exe")
                if not self.powershell or not shutil.which("wslpath"):
                    raise RuntimeError("The native CSC path needs WSL interop and PowerShell -NoProfile")
                self.program = self.directory / "PolicyTests.exe"
                shutil.copyfile(assembly, self.directory / "Newtonsoft.Json.dll")
                command = [str(compiler), "/noconfig", "/nologo", "/langversion:5", "/target:exe",
                           "/out:" + self.winpath(self.program), "/reference:" + self.winpath(self.directory / "Newtonsoft.Json.dll"),
                           "/reference:System.dll", "/reference:System.Core.dll", "/reference:System.Xml.Linq.dll", "/reference:System.Xml.dll",
                           self.winpath(source), self.winpath(harness)]
                self.native(command)
            else:
                self.dotnet = shutil.which("dotnet")
                if not self.dotnet:
                    raise RuntimeError("Actual C# policy tests are required: provide an installed .NET SDK, or CSC/NEWTONSOFT_JSON/POLICY_TEST_BUILD_ROOT. No silent skip or install.")
                sdk_lines = checked([self.dotnet, "--list-sdks"], env=self.environment).splitlines()
                if not sdk_lines:
                    raise RuntimeError("An installed .NET SDK (not just a runtime) is required")
                version, location = re.fullmatch(r"(\S+) \[(.+)\]", sdk_lines[-1]).groups()
                sdk = Path(location) / version
                compiler = sdk / "Roslyn/bincore/csc.dll"
                assembly = sdk / "Newtonsoft.Json.dll"
                dotnet_root = sdk.parent.parent
                refs_root = dotnet_root / "packs/Microsoft.NETCore.App.Ref"
                refs_version = sorted(refs_root.iterdir(), key=lambda path: tuple(int(x) for x in path.name.split(".") if x.isdigit()))[-1]
                refs = next((refs_version / "ref").iterdir())
                self.program = self.directory / "PolicyTests.dll"
                shutil.copyfile(assembly, self.directory / "Newtonsoft.Json.dll")
                command = [self.dotnet, str(compiler), "-noconfig", "-nologo", "-langversion:5", "-target:exe", "-nostdlib+",
                           "-out:" + str(self.program), "-reference:" + str(self.directory / "Newtonsoft.Json.dll")]
                command += ["-reference:" + str(path) for path in sorted(refs.glob("*.dll"))] + [str(source), str(harness)]
                checked(command, env=self.environment, cwd=self.directory)
                self.program.with_suffix(".runtimeconfig.json").write_text(json.dumps({"runtimeOptions": {
                    "tfm": refs.name, "framework": {"name": "Microsoft.NETCore.App", "version": refs_version.name}}}))
            self.identity = {"compiler": str(compiler), "compiler_sha256": sha256(compiler.read_bytes()).hexdigest(),
                             "newtonsoft": str(assembly), "newtonsoft_sha256": sha256(assembly.read_bytes()).hexdigest(),
                             "expressions_sha256": sha256(source.read_bytes()).hexdigest()}
            print("\nC# policy toolchain: " + json.dumps(self.identity, sort_keys=True), flush=True)
        except BaseException:
            self.close()
            raise

    def close(self):
        self.temporary.cleanup()

    def winpath(self, path):
        return checked(["wslpath", "-w", str(path)], env=self.environment)

    def native(self, command):
        def quote(value):
            return "'" + value.replace("'", "''") + "'"

        command = [self.winpath(command[0]) if command[0].startswith("/") else command[0], *command[1:]]
        root = quote(self.winpath(self.directory))
        script = """$ErrorActionPreference = 'Stop';
$systemRoot = [Environment]::GetEnvironmentVariable('SystemRoot', 'Process');
foreach ($name in @([Environment]::GetEnvironmentVariables('Process').Keys)) { [Environment]::SetEnvironmentVariable($name, $null, 'Process') };
$env:SystemRoot = $systemRoot; $env:WINDIR = $systemRoot;
""" + f"$root = {root};\n" + """$env:TEMP = $root; $env:TMP = $root; $env:USERPROFILE = $root;
$env:APPDATA = $root; $env:LOCALAPPDATA = $root;
$env:PATH = $systemRoot + '\\System32';
Set-Location -LiteralPath $root;
& """ + " ".join(quote(value) for value in command) + "; exit $LASTEXITCODE"
        return checked([self.powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
                       env=self.environment, cwd=self.directory)

    def run(self, requests, cache_enabled=True):
        inputs = self.directory / "inputs.json"
        inputs.write_text(json.dumps({"requests": requests, "cacheEnabled": cache_enabled}), encoding="utf-8")
        if self.windows:
            output = self.native([str(self.program), self.winpath(inputs)])
        else:
            output = checked([self.dotnet, str(self.program), str(inputs)], env=self.environment, cwd=self.directory)
        return json.loads(output.lstrip("\ufeff"))
