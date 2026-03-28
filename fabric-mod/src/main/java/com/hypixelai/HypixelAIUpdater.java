package com.hypixelai;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;

/**
 * Auto-updater for the HypixelAI mod.
 * Downloads from GitHub Releases, swaps jars on shutdown + startup.
 */
public class HypixelAIUpdater {

    public static final String MOD_VERSION = "2.1.1";
    private static final String GITHUB_REPO = "Msstarke/hypixel-skyblock-ai-bot";
    private static final String RELEASES_API = "https://api.github.com/repos/" + GITHUB_REPO + "/releases/latest";
    // Try Railway direct first (bypasses Cloudflare), then custom domain
    private static final String VERSION_CHECK_URL = "https://worker-production-f916.up.railway.app/api/mod/version";
    private static final String VERSION_CHECK_URL_2 = "https://sky-ai.uk/api/mod/version";

    private static boolean updatePending = false;
    private static String pendingVersion = null;
    private static String updateMessage = null;
    private static boolean shutdownHookRegistered = false;

    /**
     * Run on mod init — swaps .jar.update to .jar if present, cleans up .disabled files.
     */
    public static void doStartupCleanup() {
        try {
            Path modsDir = getModsDir();
            if (modsDir == null) return;

            // 1. Delete old .disabled jars (from previous update)
            try (DirectoryStream<Path> stream = Files.newDirectoryStream(modsDir, "hypixelai-mod*disabled*")) {
                for (Path p : stream) {
                    try {
                        Files.deleteIfExists(p);
                        HypixelAIMod.LOGGER.info("[HypixelAI] Deleted old: {}", p.getFileName());
                    } catch (Exception ignored) {}
                }
            }

            // 2. Delete leftover swap scripts
            try { Files.deleteIfExists(modsDir.resolve("hypixelai-swap.bat")); } catch (Exception ignored) {}
            try { Files.deleteIfExists(modsDir.resolve("hypixelai-swap.vbs")); } catch (Exception ignored) {}

            // 3. If .jar.update exists, apply it
            Path updateFile = modsDir.resolve("hypixelai-mod.jar.update");
            if (Files.exists(updateFile) && Files.size(updateFile) > 10000) {
                HypixelAIMod.LOGGER.info("[HypixelAI] Found pending update, applying...");

                // Rename all existing hypixelai jars to .disabled
                try (DirectoryStream<Path> stream = Files.newDirectoryStream(modsDir, "hypixelai-mod*.jar")) {
                    for (Path p : stream) {
                        String name = p.getFileName().toString();
                        if (name.endsWith(".update")) continue;
                        try {
                            Path disabled = p.resolveSibling(name + ".disabled");
                            Files.move(p, disabled, StandardCopyOption.REPLACE_EXISTING);
                            HypixelAIMod.LOGGER.info("[HypixelAI] Moved {} -> {}", name, disabled.getFileName());
                        } catch (Exception ex) {
                            try { Files.delete(p); } catch (Exception ignored) {}
                        }
                    }
                }

                // Rename .jar.update to .jar
                Path target = modsDir.resolve("hypixelai-mod.jar");
                Files.move(updateFile, target, StandardCopyOption.REPLACE_EXISTING);
                HypixelAIMod.LOGGER.info("[HypixelAI] Update applied! New jar: {}", target.getFileName());
            }
        } catch (Exception e) {
            HypixelAIMod.LOGGER.warn("[HypixelAI] Startup cleanup error", e);
        }
    }

    /**
     * Check GitHub for a newer version. Downloads the jar if found.
     */
    public static boolean checkForUpdate() {
        try {
            // Step 1: Quick version check via Railway direct URL (bypasses Cloudflare)
            String versionJson = httpGet(VERSION_CHECK_URL);
            String latestVersion = null;
            if (versionJson != null) {
                latestVersion = parseJsonValue(versionJson, "version");
                updateMessage = parseJsonValue(versionJson, "message");
                HypixelAIMod.LOGGER.info("[HypixelAI] Railway version check: {}", latestVersion);
            }

            // Fallback: try custom domain
            if (latestVersion == null) {
                versionJson = httpGet(VERSION_CHECK_URL_2);
                if (versionJson != null) {
                    latestVersion = parseJsonValue(versionJson, "version");
                    updateMessage = parseJsonValue(versionJson, "message");
                    HypixelAIMod.LOGGER.info("[HypixelAI] Domain version check: {}", latestVersion);
                }
            }

            // Fallback to GitHub if both didn't work
            String githubJson = null;
            if (latestVersion == null) {
                githubJson = httpGet(RELEASES_API);
                if (githubJson == null) {
                    HypixelAIMod.LOGGER.warn("[HypixelAI] Could not reach version API");
                    return false;
                }
                latestVersion = parseJsonValue(githubJson, "tag_name");
                if (latestVersion == null) return false;
                if (latestVersion.startsWith("v")) latestVersion = latestVersion.substring(1);
                updateMessage = parseJsonValue(githubJson, "body");
            }

            // Already up to date?
            if (latestVersion.equals(MOD_VERSION) || !isNewer(latestVersion, MOD_VERSION)) {
                HypixelAIMod.LOGGER.info("[HypixelAI] Up to date (v{})", MOD_VERSION);
                return false;
            }

            // Step 2: Get download URL — try Railway first, then GitHub
            String downloadUrl = "https://worker-production-f916.up.railway.app/api/mod/download";

            // Try GitHub as backup for the direct jar link
            if (githubJson == null) {
                githubJson = httpGet(RELEASES_API);
            }
            if (githubJson != null) {
                String ghUrl = findJarAssetUrl(githubJson);
                if (ghUrl != null) {
                    downloadUrl = ghUrl;
                    HypixelAIMod.LOGGER.info("[HypixelAI] Using GitHub download URL");
                } else {
                    HypixelAIMod.LOGGER.info("[HypixelAI] Using Railway download URL");
                }
            } else {
                HypixelAIMod.LOGGER.info("[HypixelAI] GitHub unavailable, using Railway download URL");
            }

            HypixelAIMod.LOGGER.info("[HypixelAI] Update available: v{} -> v{}", MOD_VERSION, latestVersion);

            Path modsDir = getModsDir();
            if (modsDir == null) {
                HypixelAIMod.LOGGER.warn("[HypixelAI] Could not find mods directory");
                return false;
            }

            // Download
            Path updateFile = modsDir.resolve("hypixelai-mod.jar.update");
            try { Files.deleteIfExists(updateFile); } catch (Exception ignored) {}

            HypixelAIMod.LOGGER.info("[HypixelAI] Downloading v{}...", latestVersion);
            boolean ok = downloadFile(downloadUrl, updateFile);
            if (!ok || !Files.exists(updateFile) || Files.size(updateFile) < 10000) {
                HypixelAIMod.LOGGER.error("[HypixelAI] Download failed or file too small");
                try { Files.deleteIfExists(updateFile); } catch (Exception ignored) {}
                return false;
            }

            HypixelAIMod.LOGGER.info("[HypixelAI] Downloaded {} bytes", Files.size(updateFile));

            // Register shutdown hook ONCE to swap jars when MC closes
            if (!shutdownHookRegistered) {
                shutdownHookRegistered = true;
                Path finalModsDir = modsDir;
                Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                    swapJars(finalModsDir);
                }, "HypixelAI-SwapHook"));
            }

            updatePending = true;
            pendingVersion = latestVersion;
            HypixelAIMod.LOGGER.info("[HypixelAI] Update ready! Restart to apply v{}", latestVersion);
            return true;

        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Update check failed", e);
            return false;
        }
    }

    /**
     * Swap jars — called from shutdown hook.
     * Renames old jars to .disabled, renames .jar.update to .jar
     */
    private static void swapJars(Path modsDir) {
        try {
            Path updateFile = modsDir.resolve("hypixelai-mod.jar.update");
            if (!Files.exists(updateFile)) return;

            // Rename old jars to .disabled
            try (DirectoryStream<Path> s = Files.newDirectoryStream(modsDir, "hypixelai-mod*.jar")) {
                for (Path p : s) {
                    String n = p.getFileName().toString();
                    if (n.endsWith(".update")) continue;
                    try {
                        Files.move(p, p.resolveSibling(n + ".disabled"), StandardCopyOption.REPLACE_EXISTING);
                    } catch (Exception ex) {
                        // On Windows, jar may still be locked — startup cleanup will handle it
                        try { Files.deleteIfExists(p); } catch (Exception ignored) {}
                    }
                }
            }

            // Rename update file
            Path target = modsDir.resolve("hypixelai-mod.jar");
            Files.move(updateFile, target, StandardCopyOption.REPLACE_EXISTING);
        } catch (Exception e) {
            // Startup cleanup will retry
        }
    }

    // --- Getters ---

    public static boolean isUpdatePending() { return updatePending; }
    public static String getPendingVersion() { return pendingVersion; }
    public static String getUpdateMessage() { return updateMessage; }

    // --- Helpers ---

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
            if (path.toString().endsWith(".jar")) return path;
        } catch (Exception ignored) {}
        return null;
    }

    private static boolean isNewer(String latest, String current) {
        String[] lp = latest.split("\\.");
        String[] cp = current.split("\\.");
        for (int i = 0; i < Math.max(lp.length, cp.length); i++) {
            int l = i < lp.length ? Integer.parseInt(lp[i]) : 0;
            int c = i < cp.length ? Integer.parseInt(cp[i]) : 0;
            if (l > c) return true;
            if (l < c) return false;
        }
        return false;
    }

    private static String findJarAssetUrl(String json) {
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
            if (url.endsWith(".jar")) return url;
            searchFrom = qEnd + 1;
        }
    }

    private static String httpGet(String urlStr) {
        try {
            URL url = URI.create(urlStr).toURL();
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setRequestProperty("Accept", "application/vnd.github+json");
            conn.setRequestProperty("User-Agent", "HypixelAI-Mod/" + MOD_VERSION);
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(10000);
            conn.setInstanceFollowRedirects(true);
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
            // Follow redirects manually (GitHub redirects to CDN)
            URL url = URI.create(urlStr).toURL();
            HttpURLConnection conn;
            int redirects = 0;
            while (redirects < 5) {
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setRequestProperty("User-Agent", "HypixelAI-Mod/" + MOD_VERSION);
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(60000);
                conn.setInstanceFollowRedirects(false); // Handle manually

                int code = conn.getResponseCode();
                if (code == 200) {
                    try (InputStream in = conn.getInputStream()) {
                        Files.copy(in, dest, StandardCopyOption.REPLACE_EXISTING);
                    }
                    conn.disconnect();
                    return true;
                } else if (code == 301 || code == 302 || code == 307) {
                    String location = conn.getHeaderField("Location");
                    conn.disconnect();
                    if (location == null) return false;
                    url = URI.create(location).toURL();
                    redirects++;
                } else {
                    conn.disconnect();
                    return false;
                }
            }
            return false;
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
