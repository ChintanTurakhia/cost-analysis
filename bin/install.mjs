#!/usr/bin/env node

import { readFileSync, writeFileSync, cpSync, rmSync, mkdirSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { homedir } from "os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PLUGIN_KEY = "cost-analysis@cost-analysis";
const MARKETPLACE_NAME = "cost-analysis";
const PLUGIN_NAME = "cost-analysis";

// Locate plugin source within this package
const pluginSource = join(__dirname, "..", "plugins", "cost-analysis");
const pluginJson = JSON.parse(
  readFileSync(join(pluginSource, ".claude-plugin", "plugin.json"), "utf8")
);
const version = pluginJson.version;

// Handle --uninstall
if (process.argv.includes("--uninstall")) {
  uninstall();
  process.exit(0);
}

install();

function install() {
  const claudeDir = join(homedir(), ".claude", "plugins");
  const cacheDest = join(claudeDir, "cache", MARKETPLACE_NAME, PLUGIN_NAME, version);
  const registryPath = join(claudeDir, "installed_plugins.json");

  // Copy plugin files to cache
  mkdirSync(cacheDest, { recursive: true });
  for (const dir of [".claude-plugin", "skills", "hooks"]) {
    const src = join(pluginSource, dir);
    if (existsSync(src)) {
      const dest = join(cacheDest, dir);
      cpSync(src, dest, { recursive: true, force: true });
    }
  }

  // Update installed_plugins.json
  let registry = { version: 2, plugins: {} };
  if (existsSync(registryPath)) {
    try {
      registry = JSON.parse(readFileSync(registryPath, "utf8"));
    } catch {
      // Corrupted file — start fresh
    }
  }

  const now = new Date().toISOString();
  registry.plugins[PLUGIN_KEY] = [
    {
      scope: "user",
      installPath: cacheDest,
      version,
      installedAt: registry.plugins[PLUGIN_KEY]?.[0]?.installedAt || now,
      lastUpdated: now,
    },
  ];

  writeFileSync(registryPath, JSON.stringify(registry, null, 2) + "\n");

  console.log(`\n  cost-analysis v${version} installed successfully.\n`);
  console.log(`  Restart Claude Code to activate.`);
  console.log(`  Run /cost-analysis:analyze to use.\n`);
}

function uninstall() {
  const claudeDir = join(homedir(), ".claude", "plugins");
  const cacheDir = join(claudeDir, "cache", MARKETPLACE_NAME);
  const registryPath = join(claudeDir, "installed_plugins.json");

  // Remove cache directory
  if (existsSync(cacheDir)) {
    rmSync(cacheDir, { recursive: true, force: true });
  }

  // Remove from registry
  if (existsSync(registryPath)) {
    try {
      const registry = JSON.parse(readFileSync(registryPath, "utf8"));
      delete registry.plugins[PLUGIN_KEY];
      writeFileSync(registryPath, JSON.stringify(registry, null, 2) + "\n");
    } catch {
      // Ignore registry errors during uninstall
    }
  }

  console.log(`\n  cost-analysis uninstalled. Restart Claude Code.\n`);
}
