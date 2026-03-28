package com.hypixelai;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;

/**
 * Auto-updater — rewritten from scratch.
 *
 * The key insight: you CANNOT swap a jar from inside the JVM on Windows.
 * Instead, spawn a hidden PowerShell process that:
 *   1. Waits for the Minecraft process to fully exit (by PID)
 *   2. Deletes the old jar (now unlocked)
 *   3. Renames .jar.update to .jar
 * This is the same approach SkyHanni/libautoupdate uses.
 */
public class HypixelAIUpdater {

    public static final String MOD_VERSION = "2.6.0";
    private static final String GITHUB_REPO = "Msstarke/hypixel-skyblock-ai-bot";
    private static final String RELEASES_API = "https://api.github.com/repos/" + GITHUB_REPO + "/releases/latest";
    private static final String VERSION_CHECK_URL = "https://worker-production-f916.up.railway.app/api/mod/version";
    private static final String VERSION_CHECK_URL_2 = "https://sky-ai.uk/api/mod/version";

    private static boolean updatePending = false;
    private static String pendingVersion = null;
    private static String updateMessage = null;
    private static boolean swapScheduled = false;

    // ── Startup cleanup ──────────────────────────────────────────────────

    public static void doStartupCleanup() {
        try {
            Path modsDir = getModsDir();
            if (modsDir == null) return;
            File[] leftovers = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && (name.endsWith(".old") || name.endsWith(".disabled")));
            if (leftovers != null) {
                for (File f : leftovers) f.delete();
            }
        } catch (Exception ignored) {}
    }

    // ── Update check ─────────────────────────────────────────────────────

    public static boolean checkForUpdate() {
        try {
            // Version check: Railway → custom domain → GitHub
            String latestVersion = null;
            String githubJson = null;

            String json = httpGet(VERSION_CHECK_URL);
            if (json != null) {
                latestVersion = parseJsonValue(json, "version");
                updateMessage = parseJsonValue(json, "message");
            }
            if (latestVersion == null) {
                json = httpGet(VERSION_CHECK_URL_2);
                if (json != null) {
                    latestVersion = parseJsonValue(json, "version");
                    updateMessage = parseJsonValue(json, "message");
                }
            }
            if (latestVersion == null) {
                githubJson = httpGet(RELEASES_API);
                if (githubJson == null) return false;
                latestVersion = parseJsonValue(githubJson, "tag_name");
                if (latestVersion == null) return false;
                if (latestVersion.startsWith("v")) latestVersion = latestVersion.substring(1);
                updateMessage = parseJsonValue(githubJson, "body");
            }

            if (latestVersion.equals(MOD_VERSION) || !isNewer(latestVersion, MOD_VERSION)) {
                HypixelAIMod.LOGGER.info("[HypixelAI] Up to date (v{})", MOD_VERSION);
                return false;
            }

            HypixelAIMod.LOGGER.info("[HypixelAI] Update: v{} -> v{}", MOD_VERSION, latestVersion);

            // Get download URL
            if (githubJson == null) githubJson = httpGet(RELEASES_API);
            String downloadUrl = githubJson != null ? findJarAssetUrl(githubJson) : null;
            if (downloadUrl == null) downloadUrl = "https://worker-production-f916.up.railway.app/api/mod/download";

            // Download
            Path modsDir = getModsDir();
            if (modsDir == null) return false;

            Path updateFile = modsDir.resolve("hypixelai-mod.jar.update");
            try { Files.deleteIfExists(updateFile); } catch (Exception ignored) {}

            HypixelAIMod.LOGGER.info("[HypixelAI] Downloading v{}...", latestVersion);
            if (!downloadFile(downloadUrl, updateFile)) return false;
            if (!Files.exists(updateFile) || Files.size(updateFile) < 10000) {
                try { Files.deleteIfExists(updateFile); } catch (Exception ignored) {}
                return false;
            }

            HypixelAIMod.LOGGER.info("[HypixelAI] Downloaded {} bytes", Files.size(updateFile));

            // Schedule the swap
            if (!swapScheduled) {
                scheduleSwap(modsDir);
                swapScheduled = true;
            }

            updatePending = true;
            pendingVersion = latestVersion;
            return true;

        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Update failed", e);
            return false;
        }
    }

    // ── The swap — runs OUTSIDE the JVM ──────────────────────────────────

    /**
     * Spawns a hidden PowerShell process that waits for Minecraft to exit,
     * then deletes the old jar and renames .jar.update to .jar.
     * PowerShell is standard on Windows 10+ and runs completely hidden.
     */
    private static void scheduleSwap(Path modsDir) {
        try {
            long pid = ProcessHandle.current().pid();
            String mp = modsDir.toAbsolutePath().toString().replace("'", "''");

            String script =
                "try { Wait-Process -Id " + pid + " -ErrorAction SilentlyContinue } catch {}; " +
                "Start-Sleep -Seconds 3; " +
                "Set-Location -LiteralPath '" + mp + "'; " +
                "if (Test-Path 'hypixelai-mod.jar.update') { " +
                    "Get-ChildItem -Filter 'hypixelai-mod*.jar' | Where-Object { $_.Name -ne 'hypixelai-mod.jar.update' } | Remove-Item -Force -ErrorAction SilentlyContinue; " +
                    "Start-Sleep -Milliseconds 500; " +
                    "Rename-Item -LiteralPath 'hypixelai-mod.jar.update' -NewName 'hypixelai-mod.jar' -Force " +
                "}";

            new ProcessBuilder(
                "powershell.exe", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", script
            )
            .redirectOutput(ProcessBuilder.Redirect.DISCARD)
            .redirectError(ProcessBuilder.Redirect.DISCARD)
            .start();

            HypixelAIMod.LOGGER.info("[HypixelAI] Swap scheduled (PID {} — will run after MC exits)", pid);
        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Failed to schedule swap: {}", e.getMessage());
        }
    }

    // ── Getters ──────────────────────────────────────────────────────────

    public static boolean isUpdatePending() { return updatePending; }
    public static String getPendingVersion() { return pendingVersion; }
    public static String getUpdateMessage() { return updateMessage; }

    // ── Internal helpers ─────────────────────────────────────────────────

    private static Path getModsDir() {
        try {
            Path jar = Path.of(HypixelAIUpdater.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI());
            if (jar.toString().endsWith(".jar") && jar.getParent() != null) return jar.getParent();
        } catch (Exception ignored) {}
        Path fallback = Path.of("mods");
        if (Files.isDirectory(fallback)) return fallback;
        return null;
    }

    private static boolean isNewer(String latest, String current) {
        String[] lp = latest.split("\\."), cp = current.split("\\.");
        for (int i = 0; i < Math.max(lp.length, cp.length); i++) {
            int l = i < lp.length ? Integer.parseInt(lp[i]) : 0;
            int c = i < cp.length ? Integer.parseInt(cp[i]) : 0;
            if (l > c) return true;
            if (l < c) return false;
        }
        return false;
    }

    private static String findJarAssetUrl(String json) {
        int from = 0;
        while (true) {
            int idx = json.indexOf("\"browser_download_url\"", from);
            if (idx == -1) return null;
            int qs = json.indexOf('"', json.indexOf(':', idx + 22) + 1);
            int qe = json.indexOf('"', qs + 1);
            String url = json.substring(qs + 1, qe);
            if (url.endsWith(".jar")) return url;
            from = qe + 1;
        }
    }

    private static String httpGet(String urlStr) {
        try {
            HttpURLConnection c = (HttpURLConnection) URI.create(urlStr).toURL().openConnection();
            c.setRequestProperty("Accept", "application/vnd.github+json");
            c.setRequestProperty("User-Agent", "HypixelAI-Mod/" + MOD_VERSION);
            c.setConnectTimeout(5000);
            c.setReadTimeout(10000);
            c.setInstanceFollowRedirects(true);
            if (c.getResponseCode() != 200) return null;
            StringBuilder sb = new StringBuilder();
            try (BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream(), StandardCharsets.UTF_8))) {
                String line; while ((line = r.readLine()) != null) sb.append(line);
            }
            c.disconnect();
            return sb.toString();
        } catch (Exception e) { return null; }
    }

    private static boolean downloadFile(String urlStr, Path dest) {
        try {
            URL url = URI.create(urlStr).toURL();
            int redirects = 0;
            while (redirects < 5) {
                HttpURLConnection c = (HttpURLConnection) url.openConnection();
                c.setRequestProperty("User-Agent", "HypixelAI-Mod/" + MOD_VERSION);
                c.setConnectTimeout(5000);
                c.setReadTimeout(60000);
                c.setInstanceFollowRedirects(false);
                int code = c.getResponseCode();
                if (code == 200) {
                    try (InputStream in = c.getInputStream()) { Files.copy(in, dest, StandardCopyOption.REPLACE_EXISTING); }
                    c.disconnect();
                    return true;
                } else if (code == 301 || code == 302 || code == 307) {
                    String loc = c.getHeaderField("Location");
                    c.disconnect();
                    if (loc == null) return false;
                    url = URI.create(loc).toURL();
                    redirects++;
                } else { c.disconnect(); return false; }
            }
            return false;
        } catch (Exception e) { return false; }
    }

    private static String parseJsonValue(String json, String key) {
        String s = "\"" + key + "\"";
        int idx = json.indexOf(s);
        if (idx == -1) return null;
        int qs = json.indexOf('"', json.indexOf(':', idx + s.length()) + 1);
        int qe = json.indexOf('"', qs + 1);
        return json.substring(qs + 1, qe);
    }
}
