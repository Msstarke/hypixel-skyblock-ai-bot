package com.hypixelai;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;

/**
 * Auto-updater for the HypixelAI mod.
 * Checks GitHub Releases for new versions, downloads and swaps jars automatically.
 */
public class HypixelAIUpdater {

    public static final String MOD_VERSION = "1.8.0";
    private static final String GITHUB_REPO = "Msstarke/hypixel-skyblock-ai-bot";
    private static final String RELEASES_API = "https://api.github.com/repos/" + GITHUB_REPO + "/releases/latest";

    private static boolean updatePending = false;
    private static String pendingVersion = null;
    private static String updateMessage = null;

    public static boolean checkForUpdate() {
        try {
            cleanupOnStartup();

            // Check GitHub for latest release
            String json = httpGet(RELEASES_API);
            if (json == null) return false;

            String latestVersion = parseJsonValue(json, "tag_name");
            if (latestVersion == null) return false;

            // Strip leading "v" if present (e.g. "v1.0.6" -> "1.0.6")
            if (latestVersion.startsWith("v")) {
                latestVersion = latestVersion.substring(1);
            }

            if (latestVersion.equals(MOD_VERSION) || !isNewer(latestVersion, MOD_VERSION)) {
                HypixelAIMod.LOGGER.info("[HypixelAI] Mod is up to date (v{})", MOD_VERSION);
                return false;
            }

            // Get release body as update message
            updateMessage = parseJsonValue(json, "body");

            // Find the jar download URL from release assets
            String downloadUrl = findJarAssetUrl(json);
            if (downloadUrl == null) {
                HypixelAIMod.LOGGER.warn("[HypixelAI] Release v{} has no jar asset", latestVersion);
                return false;
            }

            HypixelAIMod.LOGGER.info("[HypixelAI] Update available: v{} -> v{}", MOD_VERSION, latestVersion);

            Path modsDir = getModsDir();
            if (modsDir == null) {
                HypixelAIMod.LOGGER.warn("[HypixelAI] Could not find mods directory");
                return false;
            }

            // Download new jar as .jar.update (Fabric won't load this)
            Path updateFile = modsDir.resolve("hypixelai-mod.jar.update");
            if (!Files.exists(updateFile)) {
                HypixelAIMod.LOGGER.info("[HypixelAI] Downloading update from GitHub...");
                boolean ok = downloadFile(downloadUrl, updateFile);
                if (!ok) {
                    HypixelAIMod.LOGGER.error("[HypixelAI] Failed to download update");
                    return false;
                }
            }

            // Update will be applied on next startup by cleanupOnStartup()
            updatePending = true;
            pendingVersion = latestVersion;
            HypixelAIMod.LOGGER.info("[HypixelAI] Update downloaded! Will apply on next restart.");
            return true;

        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Update check failed", e);
            return false;
        }
    }

    /**
     * Find the .jar download URL from GitHub release assets JSON.
     */
    private static String findJarAssetUrl(String json) {
        // Look for browser_download_url ending in .jar
        int searchFrom = 0;
        while (true) {
            int idx = json.indexOf("\"browser_download_url\"", searchFrom);
            if (idx == -1) return null;

            int colon = json.indexOf(':', idx + 22);
            if (colon == -1) return null;

            int qStart = json.indexOf('"', colon + 1);
            if (qStart == -1) return null;

            int qEnd = json.indexOf('"', qStart + 1);
            if (qEnd == -1) return null;

            String url = json.substring(qStart + 1, qEnd);
            if (url.endsWith(".jar")) {
                return url;
            }

            searchFrom = qEnd + 1;
        }
    }

    private static void cleanupOnStartup() {
        try {
            Path modsDir = getModsDir();
            if (modsDir == null) return;

            // Delete .disabled jars
            try (DirectoryStream<Path> stream = Files.newDirectoryStream(modsDir, "hypixelai-mod*.disabled")) {
                for (Path p : stream) {
                    Files.deleteIfExists(p);
                    HypixelAIMod.LOGGER.info("[HypixelAI] Cleaned up old jar: {}", p.getFileName());
                }
            }

            // Delete swap scripts
            Files.deleteIfExists(modsDir.resolve("hypixelai-swap.bat"));
            Files.deleteIfExists(modsDir.resolve("hypixelai-swap.vbs"));

            // If .jar.update exists, the swap script didn't run — try direct swap
            Path updateFile = modsDir.resolve("hypixelai-mod.jar.update");
            if (Files.exists(updateFile)) {
                try (DirectoryStream<Path> stream = Files.newDirectoryStream(modsDir, "hypixelai-mod*.jar")) {
                    for (Path p : stream) {
                        if (!p.getFileName().toString().endsWith(".update")) {
                            Files.deleteIfExists(p);
                            HypixelAIMod.LOGGER.info("[HypixelAI] Removed old jar: {}", p.getFileName());
                        }
                    }
                }
                Path target = modsDir.resolve("hypixelai-mod.jar");
                Files.move(updateFile, target, StandardCopyOption.REPLACE_EXISTING);
                HypixelAIMod.LOGGER.info("[HypixelAI] Applied pending update on startup");
            }
        } catch (Exception e) {
            HypixelAIMod.LOGGER.warn("[HypixelAI] Startup cleanup error (non-critical)", e);
        }
    }

    public static boolean isUpdatePending() {
        return updatePending;
    }

    public static String getPendingVersion() {
        return pendingVersion;
    }

    public static String getUpdateMessage() {
        return updateMessage;
    }

    private static Path getModsDir() {
        Path jar = getCurrentJarPath();
        if (jar != null) return jar.getParent();
        Path fallback = Path.of("mods");
        if (Files.isDirectory(fallback)) return fallback;
        return null;
    }

    private static Path getCurrentJarPath() {
        try {
            URI uri = HypixelAIUpdater.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI();
            Path path = Path.of(uri);
            if (path.toString().endsWith(".jar")) {
                return path;
            }
        } catch (Exception e) {
            // ignore
        }
        return null;
    }

    private static boolean isNewer(String latest, String current) {
        String[] lParts = latest.split("\\.");
        String[] cParts = current.split("\\.");
        for (int i = 0; i < Math.max(lParts.length, cParts.length); i++) {
            int l = i < lParts.length ? Integer.parseInt(lParts[i]) : 0;
            int c = i < cParts.length ? Integer.parseInt(cParts[i]) : 0;
            if (l > c) return true;
            if (l < c) return false;
        }
        return false;
    }

    private static String httpGet(String urlStr) {
        try {
            URL url = URI.create(urlStr).toURL();
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setRequestProperty("Accept", "application/vnd.github+json");
            conn.setRequestProperty("User-Agent", "HypixelAI-Mod");
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(10000);
            if (conn.getResponseCode() != 200) return null;
            StringBuilder sb = new StringBuilder();
            try (BufferedReader r = new BufferedReader(
                    new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = r.readLine()) != null) sb.append(line);
            }
            conn.disconnect();
            return sb.toString();
        } catch (Exception e) {
            return null;
        }
    }

    private static boolean downloadFile(String urlStr, Path dest) {
        try {
            URL url = URI.create(urlStr).toURL();
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", "HypixelAI-Mod");
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(60000);
            if (conn.getResponseCode() != 200) return false;
            try (InputStream in = conn.getInputStream()) {
                Files.copy(in, dest, StandardCopyOption.REPLACE_EXISTING);
            }
            conn.disconnect();
            return true;
        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Download failed", e);
            return false;
        }
    }

    private static String parseJsonValue(String json, String key) {
        String search = "\"" + key + "\"";
        int idx = json.indexOf(search);
        if (idx == -1) return null;
        int colon = json.indexOf(':', idx + search.length());
        if (colon == -1) return null;
        int qStart = json.indexOf('"', colon + 1);
        if (qStart == -1) return null;
        int qEnd = json.indexOf('"', qStart + 1);
        if (qEnd == -1) return null;
        return json.substring(qStart + 1, qEnd);
    }
}
