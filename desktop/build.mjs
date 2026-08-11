import { downloadArtifact } from "@electron/get";
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, renameSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import extract from "extract-zip";

const desktopDir = path.dirname(fileURLToPath(import.meta.url));
const sourceDir = path.join(desktopDir, "app");
const outputDir = path.join(desktopDir, "dist");
const buildDir = path.join(outputDir, "build");
const electronVersion = "43.3.0";

function run(command, args) {
  execFileSync(command, args, { cwd: desktopDir, stdio: "inherit" });
}

async function extractElectron(platform, arch, destination) {
  const archive = await downloadArtifact({
    version: electronVersion,
    artifactName: "electron",
    platform,
    arch
  });
  mkdirSync(destination, { recursive: true });
  await extract(archive, { dir: destination });
}

function requirePaths(paths) {
  for (const requiredPath of paths) {
    if (!existsSync(requiredPath)) throw new Error(`Missing packaged file: ${requiredPath}`);
  }
}

rmSync(buildDir, { force: true, recursive: true });
mkdirSync(buildDir, { recursive: true });

const macBuild = path.join(buildDir, "macos");
await extractElectron("darwin", "arm64", macBuild);
const macApp = path.join(macBuild, "BioStonk.app");
renameSync(path.join(macBuild, "Electron.app"), macApp);
renameSync(path.join(macApp, "Contents", "MacOS", "Electron"), path.join(macApp, "Contents", "MacOS", "BioStonk"));
const macResources = path.join(macApp, "Contents", "Resources");
cpSync(sourceDir, path.join(macResources, "app"), { recursive: true });
const plist = path.join(macApp, "Contents", "Info.plist");
for (const [key, value] of [
  ["CFBundleDisplayName", "BioStonk"],
  ["CFBundleExecutable", "BioStonk"],
  ["CFBundleIdentifier", "com.biostonk.desktop"],
  ["CFBundleName", "BioStonk"]
]) {
  run("/usr/libexec/PlistBuddy", ["-c", `Set :${key} ${value}`, plist]);
}
requirePaths([path.join(macApp, "Contents", "MacOS", "BioStonk"), path.join(macResources, "app", "main.cjs")]);
run("codesign", ["--force", "--deep", "--sign", "-", macApp]);
const dmgPath = path.join(outputDir, "BioStonk-macOS.dmg");
rmSync(dmgPath, { force: true });
run("hdiutil", ["create", "-volname", "BioStonk", "-srcfolder", macApp, "-ov", "-format", "UDZO", dmgPath]);

const windowsApp = path.join(buildDir, "windows", "BioStonk-Windows");
await extractElectron("win32", "x64", windowsApp);
renameSync(path.join(windowsApp, "electron.exe"), path.join(windowsApp, "BioStonk.exe"));
cpSync(sourceDir, path.join(windowsApp, "resources", "app"), { recursive: true });
requirePaths([
  path.join(windowsApp, "BioStonk.exe"),
  path.join(windowsApp, "resources", "app", "main.cjs"),
  path.join(windowsApp, "resources", "default_app.asar")
]);
const zipPath = path.join(outputDir, "BioStonk-Windows.zip");
rmSync(zipPath, { force: true });
run("ditto", ["-c", "-k", "--norsrc", "--keepParent", windowsApp, zipPath]);

for (const artifact of [dmgPath, zipPath]) console.log(`Created ${artifact}`);