package com.hypixelai;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.message.v1.ClientSendMessageEvents;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.util.InputUtil;
import net.minecraft.text.MutableText;
import net.minecraft.text.Text;
import net.minecraft.util.Formatting;
import net.minecraft.util.Identifier;
import org.lwjgl.glfw.GLFW;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class HypixelAIClient implements ClientModInitializer {

    private static long lastRequest = 0;
    private static final long COOLDOWN_MS = 3000;

    // Keybinds
    private static KeyBinding keyCorrect;
    private static KeyBinding keyWrong;
    private static KeyBinding keyConfig;

    // Color scheme
    private static final Formatting ACCENT = Formatting.GOLD;
    private static final Formatting BRAND = Formatting.AQUA;
    private static final Formatting BODY = Formatting.GRAY;
    private static final Formatting HIGHLIGHT = Formatting.WHITE;
    private static final Formatting SUCCESS = Formatting.GREEN;
    private static final Formatting ERROR = Formatting.RED;
    private static final Formatting MUTED = Formatting.DARK_GRAY;

    @Override
    public void onInitializeClient() {
        HypixelAIConfig.load();

        // Register HUD overlays
        SkyAIOverlay.register();
        CortisolBar.register();

        // Register feedback keybinds
        KeyBinding.Category skyaiCategory = KeyBinding.Category.create(
                Identifier.of("hypixelai", "category"));
        keyCorrect = KeyBindingHelper.registerKeyBinding(new KeyBinding(
                "key.hypixelai.correct", InputUtil.Type.KEYSYM, GLFW.GLFW_KEY_Y,
                skyaiCategory));
        keyWrong = KeyBindingHelper.registerKeyBinding(new KeyBinding(
                "key.hypixelai.wrong", InputUtil.Type.KEYSYM, GLFW.GLFW_KEY_N,
                skyaiCategory));
        keyConfig = KeyBindingHelper.registerKeyBinding(new KeyBinding(
                "key.hypixelai.config", InputUtil.Type.KEYSYM, GLFW.GLFW_KEY_RIGHT_SHIFT,
                skyaiCategory));

        // Check for updates in background
        new Thread(() -> HypixelAIUpdater.checkForUpdate(), "HypixelAI-Updater").start();

        // Update checking + notifications
        final boolean[] autoRegistered = {false};
        final boolean[] wasInWorld = {false};
        final long[] lastUpdateCheck = {0};
        final long UPDATE_CHECK_INTERVAL = 30 * 60 * 1000; // 30 minutes

        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            // Handle feedback keybinds
            if (client.player != null && SkyAIOverlay.hasPendingFeedback()) {
                if (keyCorrect.wasPressed()) {
                    handleFeedback("up");
                }
                if (keyWrong.wasPressed()) {
                    handleFeedback("down");
                }
            }

            // Detect joining a world/server
            if (client.player != null && !wasInWorld[0]) {
                wasInWorld[0] = true;
                // Show mod info on every world join
                sendChat(Text.empty());
                sendChat(prefix()
                        .append(Text.literal("SkyAI").formatted(BRAND, Formatting.BOLD))
                        .append(Text.literal(" v" + HypixelAIUpdater.MOD_VERSION).formatted(MUTED))
                        .append(Text.literal(" | ").formatted(MUTED))
                        .append(Text.literal("!ai <question>").formatted(BODY))
                        .append(Text.literal(" | ").formatted(MUTED))
                        .append(Text.literal("!aihelp").formatted(BODY)));
                if (HypixelAIUpdater.isUpdatePending()) {
                    sendChat(prefix()
                            .append(Text.literal("Update ready! ").formatted(SUCCESS))
                            .append(Text.literal("v" + HypixelAIUpdater.getPendingVersion()).formatted(SUCCESS, Formatting.BOLD))
                            .append(Text.literal(" — restart to apply.").formatted(MUTED)));
                }
                sendChat(Text.empty());

                // Check for updates immediately on world join
                if (!HypixelAIUpdater.isUpdatePending()) {
                    lastUpdateCheck[0] = System.currentTimeMillis();
                    new Thread(() -> {
                        boolean found = HypixelAIUpdater.checkForUpdate();
                        if (found) {
                            sendChat(Text.empty());
                            sendChat(prefix()
                                    .append(Text.literal("Update downloaded! ").styled(s -> s.withColor(Formatting.GREEN)))
                                    .append(Text.literal("v" + HypixelAIUpdater.MOD_VERSION).formatted(MUTED))
                                    .append(Text.literal(" \u2192 ").formatted(MUTED))
                                    .append(Text.literal("v" + HypixelAIUpdater.getPendingVersion()).formatted(SUCCESS, Formatting.BOLD)));
                            sendChat(prefix().append(Text.literal("Restart to apply.").formatted(MUTED)));
                            sendChat(Text.empty());
                        }
                    }, "HypixelAI-JoinUpdate").start();
                }
            }
            if (client.player == null && wasInWorld[0]) {
                wasInWorld[0] = false; // Reset when leaving world
            }

            // Auto-register/activate when player joins world
            if (!autoRegistered[0] && client.player != null) {
                autoRegistered[0] = true;
                new Thread(() -> {
                    if (!HypixelAIConfig.getLicenseKey().isEmpty()) {
                        activateLicense(HypixelAIConfig.getLicenseKey(), true);
                    } else {
                        autoRegister();
                    }
                }, "HypixelAI-Auth").start();
            }

            // Periodic update check while running
            if (client.player != null) {
                long now = System.currentTimeMillis();
                if (now - lastUpdateCheck[0] > UPDATE_CHECK_INTERVAL) {
                    lastUpdateCheck[0] = now;
                    if (!HypixelAIUpdater.isUpdatePending()) {
                        new Thread(() -> {
                            boolean found = HypixelAIUpdater.checkForUpdate();
                            if (found) {
                                // Notify immediately in chat
                                sendChat(Text.empty());
                                sendChat(prefix()
                                        .append(Text.literal("Update downloaded! ").styled(s -> s.withColor(Formatting.GREEN)))
                                        .append(Text.literal("v" + HypixelAIUpdater.MOD_VERSION).formatted(MUTED))
                                        .append(Text.literal(" \u2192 ").formatted(MUTED))
                                        .append(Text.literal("v" + HypixelAIUpdater.getPendingVersion()).formatted(SUCCESS, Formatting.BOLD)));
                                String msg = HypixelAIUpdater.getUpdateMessage();
                                if (msg != null && !msg.isEmpty()) {
                                    sendChat(Text.literal("   " + msg).formatted(BODY));
                                }
                                sendChat(Text.literal("   Restart your game to apply.").formatted(MUTED));
                                sendChat(Text.empty());
                            }
                        }, "HypixelAI-UpdateCheck").start();
                    }
                }
            }
        });

        // Intercept outgoing chat messages
        ClientSendMessageEvents.ALLOW_CHAT.register((message) -> {
            String lower = message.toLowerCase();

            if (lower.startsWith("!ai ")) {
                handleQuestion(message.substring(4).trim());
                return false;
            }
            if (lower.equals("!ai")) {
                showHelp();
                return false;
            }
            if (lower.startsWith("!aiconfig ")) {
                handleConfig(message.substring(10).trim());
                return false;
            }
            if (lower.equals("!aiconfig")) {
                showConfig();
                return false;
            }
            if (lower.equals("!aihelp") || lower.equals("!commands") || lower.equals("!help")) {
                showHelp();
                return false;
            }

            if (lower.startsWith("!aikey ")) {
                handleActivateKey(message.substring(7).trim());
                return false;
            }
            if (lower.equals("!aikey")) {
                if (HypixelAIConfig.hasSession()) {
                    sendChat(prefix().append(Text.literal("License active.").formatted(SUCCESS)));
                } else {
                    sendChat(prefix().append(Text.literal("Usage: ").formatted(BODY))
                            .append(Text.literal("!aikey <license-key>").formatted(HIGHLIGHT)));
                }
                return false;
            }

            if (lower.startsWith("!link ")) {
                handleLink(message.substring(6).trim());
                return false;
            }
            if (lower.equals("!link")) {
                sendChat(prefix().append(Text.literal("Usage: ").formatted(BODY))
                        .append(Text.literal("!link <ign>").formatted(HIGHLIGHT)));
                return false;
            }
            if (lower.equals("!unlink")) {
                handleUnlink();
                return false;
            }
            if (lower.equals("!correct") || lower.equals("!right") || lower.equals("!good")) {
                handleFeedback("up");
                return false;
            }
            if (lower.equals("!wrong") || lower.equals("!bad") || lower.equals("!incorrect")) {
                handleFeedback("down");
                return false;
            }
            if (lower.equals("!wind")) {
                handleWind();
                return false;
            }
            if (lower.equals("!version") || lower.equals("!aiversion")) {
                sendChat(Text.empty());
                sendChat(prefix().append(Text.literal("SkyAI").formatted(BRAND, Formatting.BOLD))
                        .append(Text.literal(" v" + HypixelAIUpdater.MOD_VERSION).formatted(HIGHLIGHT)));
                sendChat(Text.literal("  MC 1.21.10 | Fabric | sky-ai.uk").formatted(MUTED));
                sendChat(Text.empty());
                return false;
            }
            if (lower.equals("!aiupdate")) {
                sendChat(prefix().append(Text.literal("Checking for updates...").formatted(BODY)));
                new Thread(() -> {
                    boolean found = HypixelAIUpdater.checkForUpdate();
                    if (found) {
                        sendChat(prefix()
                                .append(Text.literal("Update found! ").formatted(SUCCESS))
                                .append(Text.literal("v" + HypixelAIUpdater.MOD_VERSION).formatted(MUTED))
                                .append(Text.literal(" \u2192 ").formatted(MUTED))
                                .append(Text.literal("v" + HypixelAIUpdater.getPendingVersion()).formatted(SUCCESS, Formatting.BOLD)));
                        sendChat(prefix().append(Text.literal("Restart to apply.").formatted(BODY)));
                    } else if (HypixelAIUpdater.isUpdatePending()) {
                        sendChat(prefix()
                                .append(Text.literal("Update already downloaded: ").formatted(BODY))
                                .append(Text.literal("v" + HypixelAIUpdater.getPendingVersion()).formatted(SUCCESS)));
                        sendChat(prefix().append(Text.literal("Restart to apply.").formatted(BODY)));
                    } else {
                        sendChat(prefix()
                                .append(Text.literal("You're up to date! ").formatted(SUCCESS))
                                .append(Text.literal("v" + HypixelAIUpdater.MOD_VERSION).formatted(MUTED)));
                    }
                }, "HypixelAI-ManualUpdate").start();
                return false;
            }
            return true;
        });

        HypixelAIMod.LOGGER.info("[HypixelAI] Client mod loaded v{}", HypixelAIUpdater.MOD_VERSION);
    }


    // ── License activation ───────────────────────────────────────────────

    private void handleActivateKey(String key) {
        if (key.isEmpty()) {
            sendChat(prefix().append(Text.literal("Usage: ").formatted(BODY))
                    .append(Text.literal("!aikey <license-key>").formatted(HIGHLIGHT)));
            return;
        }

        sendChat(prefix().append(Text.literal("Activating license...").formatted(BODY)));
        new Thread(() -> activateLicense(key, false), "HypixelAI-Activate").start();
    }

    private void activateLicense(String key, boolean silent) {
        try {
            String uuid = getUUID();
            String username = getUsername();

            String payload = "{\"license_key\":" + jsonEscape(key)
                    + ",\"mc_uuid\":" + jsonEscape(uuid)
                    + ",\"username\":" + jsonEscape(username) + "}";

            URL url = URI.create(HypixelAIConfig.getActivateUrl()).toURL();
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            conn.setDoOutput(true);
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(10000);

            try (OutputStream os = conn.getOutputStream()) {
                os.write(payload.getBytes(StandardCharsets.UTF_8));
            }

            int code = conn.getResponseCode();
            String body = readStream(code == 200 ? conn.getInputStream() : conn.getErrorStream());
            conn.disconnect();

            if (code == 200) {
                // Parse session token from response
                String session = parseStringField(body, "\"session\"", 0);
                String plan = parseStringField(body, "\"plan\"", 0);

                HypixelAIConfig.setLicenseKey(key);
                HypixelAIConfig.setSessionToken(session);

                if (!silent) {
                    sendChat(prefix().append(Text.literal("\u2714 License activated! ").formatted(SUCCESS))
                            .append(Text.literal("Plan: " + plan).formatted(BRAND)));
                }
                HypixelAIMod.LOGGER.info("[HypixelAI] License activated (plan={})", plan);
            } else {
                String error = parseStringField(body, "\"error\"", 0);
                if (!silent) {
                    sendChat(prefix().append(Text.literal("\u2716 ").formatted(ERROR))
                            .append(Text.literal(error.isEmpty() ? "Activation failed" : error).formatted(BODY)));
                }
                HypixelAIMod.LOGGER.warn("[HypixelAI] Activation failed: {} ({})", error, code);
            }
        } catch (Exception e) {
            if (!silent) {
                sendChat(prefix().append(Text.literal("\u2716 Activation failed: ").formatted(ERROR))
                        .append(Text.literal(e.getMessage()).formatted(MUTED)));
            }
        }
    }

    private void autoRegister() {
        try {
            String uuid = getUUID();
            String username = getUsername();
            if (uuid.isEmpty()) return;

            String payload = "{\"mc_uuid\":" + jsonEscape(uuid)
                    + ",\"username\":" + jsonEscape(username) + "}";

            URL url = URI.create(HypixelAIConfig.getBaseUrl() + "/api/register").toURL();
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            conn.setDoOutput(true);
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(10000);

            try (OutputStream os = conn.getOutputStream()) {
                os.write(payload.getBytes(StandardCharsets.UTF_8));
            }

            int code = conn.getResponseCode();
            String body = readStream(code == 200 ? conn.getInputStream() : conn.getErrorStream());
            conn.disconnect();

            if (code == 200) {
                String session = parseStringField(body, "\"session\"", 0);
                String plan = parseStringField(body, "\"plan\"", 0);
                String key = parseStringField(body, "\"license_key\"", 0);

                HypixelAIConfig.setLicenseKey(key);
                HypixelAIConfig.setSessionToken(session);

                sendChat(prefix().append(Text.literal("Free tier activated! ").formatted(SUCCESS))
                        .append(Text.literal("(10 questions/hr)").formatted(MUTED)));
                sendChat(prefix().append(Text.literal("Upgrade with ").formatted(BODY))
                        .append(Text.literal("!aikey <key>").formatted(HIGHLIGHT))
                        .append(Text.literal(" for unlimited access.").formatted(BODY)));

                HypixelAIMod.LOGGER.info("[HypixelAI] Free tier auto-registered (plan={})", plan);
            }
        } catch (Exception e) {
            HypixelAIMod.LOGGER.warn("[HypixelAI] Auto-register failed: {}", e.getMessage());
        }
    }


    // ── Question handling ────────────────────────────────────────────────

    private void handleQuestion(String question) {
        if (question.isEmpty()) {
            showHelp();
            return;
        }

        // Check if activated
        if (!HypixelAIConfig.hasSession()) {
            sendChat(prefix().append(Text.literal("Still connecting... try again in a moment.").formatted(Formatting.YELLOW)));
            return;
        }

        // Cooldown
        long now = System.currentTimeMillis();
        if (now - lastRequest < COOLDOWN_MS) {
            sendChat(prefix().append(Text.literal("Slow down! Wait a moment.").formatted(Formatting.YELLOW)));
            return;
        }
        lastRequest = now;

        SkyAIOverlay.showThinking(question);

        String username = getUsername();
        new Thread(() -> {
            try {
                String response = callAPI(question, username);
                if (response != null) {
                    displayResponse(question, response);
                } else {
                    SkyAIOverlay.clear();
                }
            } catch (Exception e) {
                HypixelAIMod.LOGGER.error("[HypixelAI] API call failed", e);
                SkyAIOverlay.clear();
                sendChat(prefix().append(Text.literal("\u2716 ").formatted(ERROR))
                        .append(Text.literal(e.getMessage()).formatted(MUTED)));
            }
        }, "HypixelAI-API").start();
    }

    private String callAPI(String question, String username) throws Exception {
        String apiUrl = HypixelAIConfig.getApiUrl();
        String session = HypixelAIConfig.getSessionToken();

        URL url = URI.create(apiUrl).toURL();
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
        conn.setDoOutput(true);
        conn.setConnectTimeout(5000);
        conn.setReadTimeout(30000);

        String payload = "{\"question\":" + jsonEscape(question)
                + ",\"session\":" + jsonEscape(session)
                + ",\"username\":" + jsonEscape(username) + "}";

        try (OutputStream os = conn.getOutputStream()) {
            os.write(payload.getBytes(StandardCharsets.UTF_8));
        }

        int code = conn.getResponseCode();

        if (code == 200) {
            return readStream(conn.getInputStream());
        } else if (code == 401) {
            // Session expired — try to re-activate
            String key = HypixelAIConfig.getLicenseKey();
            if (!key.isEmpty()) {
                activateLicense(key, true);
                // Retry once with new session
                if (HypixelAIConfig.hasSession()) {
                    conn.disconnect();
                    return callAPI(question, username);
                }
            }
            sendChat(prefix().append(Text.literal("\u2716 Session expired. Use !aikey to re-activate.").formatted(ERROR)));
        } else if (code == 429) {
            sendChat(prefix().append(Text.literal("\u2716 Rate limit reached. Try again later.").formatted(Formatting.YELLOW)));
        } else if (code == 503) {
            sendChat(prefix().append(Text.literal("\u231B Bot is starting up, try again.").formatted(Formatting.YELLOW)));
        } else {
            sendChat(prefix().append(Text.literal("\u2716 HTTP " + code).formatted(ERROR)));
        }

        conn.disconnect();
        return null;
    }


    // ── Link / Unlink ────────────────────────────────────────────────────

    private void handleLink(String ign) {
        if (ign.isEmpty()) {
            sendChat(prefix().append(Text.literal("Usage: ").formatted(BODY))
                    .append(Text.literal("!link <ign>").formatted(HIGHLIGHT)));
            return;
        }

        String username = getUsername();
        sendChat(prefix().append(Text.literal("Linking to ").formatted(BODY))
                .append(Text.literal(ign).formatted(BRAND))
                .append(Text.literal("...").formatted(BODY)));

        new Thread(() -> {
            try {
                String baseUrl = HypixelAIConfig.getBaseUrl();
                String payload = "{\"username\":" + jsonEscape(username)
                        + ",\"ign\":" + jsonEscape(ign)
                        + ",\"session\":" + jsonEscape(HypixelAIConfig.getSessionToken()) + "}";

                URL url = URI.create(baseUrl + "/api/link").toURL();
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setDoOutput(true);
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(10000);

                try (OutputStream os = conn.getOutputStream()) {
                    os.write(payload.getBytes(StandardCharsets.UTF_8));
                }

                int code = conn.getResponseCode();
                conn.disconnect();

                if (code == 200) {
                    sendChat(prefix().append(Text.literal("\u2714 ").formatted(SUCCESS))
                            .append(Text.literal("Linked to ").formatted(BODY))
                            .append(Text.literal(ign).formatted(BRAND))
                            .append(Text.literal(" \u2014 responses are now personalized.").formatted(BODY)));
                } else {
                    sendChat(prefix().append(Text.literal("\u2716 Failed to link ").formatted(ERROR))
                            .append(Text.literal("(HTTP " + code + ")").formatted(MUTED)));
                }
            } catch (Exception e) {
                sendChat(prefix().append(Text.literal("\u2716 Link failed: ").formatted(ERROR))
                        .append(Text.literal(e.getMessage()).formatted(MUTED)));
            }
        }, "HypixelAI-Link").start();
    }

    private void handleUnlink() {
        String username = getUsername();

        new Thread(() -> {
            try {
                String baseUrl = HypixelAIConfig.getBaseUrl();
                String payload = "{\"username\":" + jsonEscape(username)
                        + ",\"session\":" + jsonEscape(HypixelAIConfig.getSessionToken()) + "}";

                URL url = URI.create(baseUrl + "/api/unlink").toURL();
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setDoOutput(true);
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(10000);

                try (OutputStream os = conn.getOutputStream()) {
                    os.write(payload.getBytes(StandardCharsets.UTF_8));
                }

                int code = conn.getResponseCode();
                conn.disconnect();

                if (code == 200) {
                    sendChat(prefix().append(Text.literal("\u2714 Unlinked.").formatted(Formatting.YELLOW)));
                } else {
                    sendChat(prefix().append(Text.literal("\u2716 Failed to unlink ").formatted(ERROR))
                            .append(Text.literal("(HTTP " + code + ")").formatted(MUTED)));
                }
            } catch (Exception e) {
                sendChat(prefix().append(Text.literal("\u2716 Unlink failed: ").formatted(ERROR))
                        .append(Text.literal(e.getMessage()).formatted(MUTED)));
            }
        }, "HypixelAI-Unlink").start();
    }


    // ── Feedback ─────────────────────────────────────────────────────────

    private void handleFeedback(String vote) {
        if (!SkyAIOverlay.hasPendingFeedback()) {
            sendChat(prefix().append(Text.literal("No response to rate right now.").formatted(MUTED)));
            return;
        }

        String label = vote.equals("up") ? "\u2714 Correct" : "\u2716 Wrong";
        Formatting color = vote.equals("up") ? SUCCESS : ERROR;
        SkyAIOverlay.setFeedback(vote);
        sendChat(prefix().append(Text.literal("Feedback: ").formatted(BODY))
                .append(Text.literal(label).formatted(color))
                .append(Text.literal(" \u2014 thanks!").formatted(BODY)));

        String question = SkyAIOverlay.getLastQuestion();
        String response = SkyAIOverlay.getLastResponse();
        String username = getUsername();

        new Thread(() -> {
            try {
                String baseUrl = HypixelAIConfig.getBaseUrl();
                String payload = "{\"vote\":" + jsonEscape(vote)
                        + ",\"username\":" + jsonEscape(username)
                        + ",\"question\":" + jsonEscape(question != null ? question : "")
                        + ",\"response\":" + jsonEscape(response != null ? response : "")
                        + ",\"session\":" + jsonEscape(HypixelAIConfig.getSessionToken()) + "}";

                URL url = URI.create(baseUrl + "/api/feedback").toURL();
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setDoOutput(true);
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(10000);

                try (OutputStream os = conn.getOutputStream()) {
                    os.write(payload.getBytes(StandardCharsets.UTF_8));
                }

                conn.getResponseCode();
                conn.disconnect();
            } catch (Exception e) {
                HypixelAIMod.LOGGER.warn("[HypixelAI] Feedback send failed: {}", e.getMessage());
            }
        }, "HypixelAI-Feedback").start();
    }


    // ── Display ──────────────────────────────────────────────────────────

    private void displayResponse(String question, String jsonBody) {
        String[] lines = parseChatLines(jsonBody);
        if (lines.length == 0) {
            SkyAIOverlay.clear();
            sendChat(prefix().append(Text.literal("No response.").formatted(MUTED)));
            return;
        }

        // Parse HOTM data if present
        int[] hotmPerks = parseHotmData(jsonBody);

        // Show in the HUD overlay
        SkyAIOverlay.show(question, lines, hotmPerks);
    }

    private void showConfig() {
        String[][] settings = HypixelAIConfig.getAllSettings();
        sendChat(Text.empty());
        sendChat(prefix().append(Text.literal("Settings").formatted(ACCENT, Formatting.BOLD)));
        for (String[] s : settings) {
            boolean on = s[1].equals("ON");
            sendChat(Text.literal("  ").formatted(BODY)
                    .append(Text.literal(on ? "\u25C9 " : "\u25CB ").formatted(on ? SUCCESS : ERROR))
                    .append(Text.literal(s[0]).formatted(HIGHLIGHT))
                    .append(Text.literal(" \u2014 ").formatted(MUTED))
                    .append(Text.literal(s[2]).formatted(BODY))
                    .append(Text.literal(" [" + s[1] + "]").formatted(on ? SUCCESS : ERROR)));
        }
        sendChat(Text.literal("  ").formatted(BODY)
                .append(Text.literal("Toggle: ").formatted(MUTED))
                .append(Text.literal("!aiconfig <setting>").formatted(HIGHLIGHT)));
        sendChat(Text.empty());
    }

    private void handleConfig(String setting) {
        if (setting.isEmpty()) {
            showConfig();
            return;
        }

        Boolean newValue = HypixelAIConfig.toggle(setting);
        if (newValue == null) {
            sendChat(prefix().append(Text.literal("Unknown setting: ").formatted(ERROR))
                    .append(Text.literal(setting).formatted(HIGHLIGHT))
                    .append(Text.literal(". Type !aiconfig to see all.").formatted(MUTED)));
            return;
        }

        String label = setting.toLowerCase();
        sendChat(prefix()
                .append(Text.literal(label).formatted(HIGHLIGHT))
                .append(Text.literal(" \u2192 ").formatted(MUTED))
                .append(Text.literal(newValue ? "ON" : "OFF").formatted(newValue ? SUCCESS : ERROR)));
    }

    private void handleWind() {
        int speed = 100 + new java.util.Random().nextInt(101); // 100-200
        String[] directions = {"N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"};
        String dir = directions[new java.util.Random().nextInt(directions.length)];
        int gusts = speed + 15 + new java.util.Random().nextInt(30);
        String cat = speed < 130 ? "4" : "5";
        String[] warnings = {
            "SEEK SHELTER IMMEDIATELY",
            "WARNING: Category 5 Hurricane detected",
            "Your house is gone. Accept it.",
            "Wind advisory: DO NOT go outside. Ever.",
            "FEMA has been notified. They said good luck.",
            "Trees are now projectiles. Stay indoors.",
            "The cows are flying. This is not a drill.",
            "Your roof called. It's in the next state.",
            "Wind speed exceeds legal limits. Wind has been arrested.",
            "God is blowing on your Minecraft world.",
        };
        String warning = warnings[new java.util.Random().nextInt(warnings.length)];

        // Send to party chat
        MinecraftClient client = MinecraftClient.getInstance();
        if (client != null && client.getNetworkHandler() != null) {
            client.getNetworkHandler().sendChatMessage("/pc [WEATHER ALERT] Wind: " + speed + " mph " + dir + " | Gusts: " + gusts + " mph (Cat " + cat + ") | " + warning);
        }
    }

    private void showHelp() {
        String[] helpLines = {
                "Commands:",
                "",
                "- !ai <question>  \u2014  Ask anything about Skyblock",
                "- !aikey <key>  \u2014  Upgrade to paid plan",
                "- !aiconfig  \u2014  Toggle settings (HUD, cortisol, etc)",
                "- !wind  \u2014  Check wind speed",
                "- !link <ign>  \u2014  Link your account",
                "- !unlink  \u2014  Remove linked account",
                "- !correct / !wrong  \u2014  Rate the AI response",
                "",
                "Free tier: 10 questions/hr",
                "Basic ($4.99/mo): 30/hr | Pro ($9.99/mo): 100/hr",
                "",
                "Examples:",
                "",
                "1. !ai best money making method",
                "2. !ai what pet for mining",
                "3. !ai what should i upgrade next",
        };
        SkyAIOverlay.show("Help", helpLines);
    }


    // --- Utilities ---

    private static MutableText prefix() {
        return Text.literal("\u2B25 ").formatted(ACCENT)
                .append(Text.literal("SkyAI").formatted(BRAND, Formatting.BOLD))
                .append(Text.literal(" \u00BB ").formatted(MUTED));
    }

    private static void sendChat(Text text) {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client != null && client.inGameHud != null) {
            client.execute(() -> client.inGameHud.getChatHud().addMessage(text));
        }
    }

    private static String getUsername() {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client != null && client.getSession() != null) {
            return client.getSession().getUsername();
        }
        return "";
    }

    private static String getUUID() {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client != null && client.getSession() != null) {
            return client.getSession().getUuidOrNull() != null
                    ? client.getSession().getUuidOrNull().toString()
                    : "";
        }
        return "";
    }

    private static String readStream(InputStream is) throws IOException {
        if (is == null) return "{}";
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }

    private static String jsonEscape(String s) {
        if (s == null) return "\"\"";
        StringBuilder sb = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default: sb.append(c);
            }
        }
        sb.append("\"");
        return sb.toString();
    }

    /**
     * Parse HOTM data from JSON response for pixel art rendering.
     */
    private static int[] parseHotmData(String json) {
        int hotmIdx = json.indexOf("\"hotm\"");
        if (hotmIdx == -1) return null;

        int levelVal = parseIntField(json, "\"level\"", hotmIdx);
        if (levelVal < 0) return null;

        String selectedAbility = parseStringField(json, "\"selected_ability\"", hotmIdx);

        int perksIdx = json.indexOf("\"perks\"", hotmIdx);
        if (perksIdx == -1) return null;

        String[][] TREE = {
            {null, null, null, "mining_speed", null, null, null},
            {null, "mining_speed_boost", "precision_mining", "mining_fortune", "titanium_insanium", "pickaxe_toss", null},
            {null, "random_event", null, "efficient_miner", null, "forge_time", null},
            {"daily_effect", "old_school", "professional", "mole", "fortunate", "mining_experience", "front_loaded"},
            {null, "daily_grind", null, "special_0", null, "daily_powder", null},
            {"anomalous_desire", "blockhead", "subterranean_fisher", "keep_it_cool", "lonesome_miner", "great_explorer", "maniac_miner"},
            {null, "mining_speed_2", null, "powder_buff", null, "mining_fortune_2", null},
            {"miners_blessing", "no_stone_unturned", "strong_arm", "steady_hand", "warm_hearted", "surveyor", "mineshaft_mayhem"},
            {null, "metal_head", null, "rags_to_riches", null, "eager_adventurer", null},
            {"gemstone_infusion", "crystalline", "gifts_from_the_departed", "mining_master", "hungry_for_more", "vanguard_seeker", "sheer_force"},
        };

        java.util.Set<String> ABILITIES = new java.util.HashSet<>(java.util.Arrays.asList(
            "mining_speed_boost", "pickaxe_toss", "anomalous_desire", "maniac_miner", "gemstone_infusion", "sheer_force"
        ));

        java.util.Map<String, Integer> maxLevels = new java.util.HashMap<>();
        maxLevels.put("mining_speed", 50); maxLevels.put("mining_speed_boost", 1); maxLevels.put("precision_mining", 1);
        maxLevels.put("mining_fortune", 50); maxLevels.put("titanium_insanium", 50); maxLevels.put("pickaxe_toss", 1);
        maxLevels.put("random_event", 45); maxLevels.put("efficient_miner", 100); maxLevels.put("forge_time", 20);
        maxLevels.put("daily_effect", 1); maxLevels.put("old_school", 20); maxLevels.put("professional", 140);
        maxLevels.put("mole", 200); maxLevels.put("fortunate", 20); maxLevels.put("mining_experience", 100);
        maxLevels.put("front_loaded", 1); maxLevels.put("daily_grind", 1); maxLevels.put("special_0", 10);
        maxLevels.put("daily_powder", 1); maxLevels.put("anomalous_desire", 1); maxLevels.put("blockhead", 20);
        maxLevels.put("subterranean_fisher", 40); maxLevels.put("keep_it_cool", 50); maxLevels.put("lonesome_miner", 45);
        maxLevels.put("great_explorer", 20); maxLevels.put("maniac_miner", 1); maxLevels.put("mining_speed_2", 50);
        maxLevels.put("powder_buff", 50); maxLevels.put("mining_fortune_2", 50); maxLevels.put("miners_blessing", 1);
        maxLevels.put("no_stone_unturned", 50); maxLevels.put("strong_arm", 100); maxLevels.put("steady_hand", 100);
        maxLevels.put("warm_hearted", 50); maxLevels.put("surveyor", 20); maxLevels.put("mineshaft_mayhem", 1);
        maxLevels.put("metal_head", 20); maxLevels.put("rags_to_riches", 50); maxLevels.put("eager_adventurer", 100);
        maxLevels.put("gemstone_infusion", 1); maxLevels.put("crystalline", 50); maxLevels.put("gifts_from_the_departed", 100);
        maxLevels.put("mining_master", 10); maxLevels.put("hungry_for_more", 50); maxLevels.put("vanguard_seeker", 50);
        maxLevels.put("sheer_force", 1);

        int[] grid = new int[70];

        for (int tier = 0; tier < 10; tier++) {
            boolean locked = (tier + 1) > levelVal;
            for (int col = 0; col < 7; col++) {
                String perkId = TREE[tier][col];
                int idx = tier * 7 + col;
                if (perkId == null) {
                    grid[idx] = 0;
                } else if (locked) {
                    grid[idx] = -1;
                } else {
                    int perkLevel = parseIntField(json, "\"" + perkId + "\"", perksIdx);
                    if (perkLevel < 0) perkLevel = 0;
                    boolean isAbility = ABILITIES.contains(perkId);
                    int maxLvl = maxLevels.getOrDefault(perkId, 1);

                    if (isAbility && perkLevel > 0) {
                        grid[idx] = (perkId.equals(selectedAbility)) ? 5 : 4;
                    } else if (perkLevel >= maxLvl && perkLevel > 0) {
                        grid[idx] = 3;
                    } else if (perkLevel > 0) {
                        grid[idx] = 2;
                    } else {
                        grid[idx] = 1;
                    }
                }
            }
        }
        return grid;
    }

    private static int parseIntField(String json, String key, int searchFrom) {
        int idx = json.indexOf(key, searchFrom);
        if (idx == -1) return -1;
        int colon = json.indexOf(':', idx + key.length());
        if (colon == -1) return -1;
        int start = colon + 1;
        while (start < json.length() && (json.charAt(start) == ' ' || json.charAt(start) == '"')) start++;
        int end = start;
        while (end < json.length() && (Character.isDigit(json.charAt(end)) || json.charAt(end) == '.')) end++;
        if (end == start) return -1;
        try {
            return (int) Double.parseDouble(json.substring(start, end));
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    private static String parseStringField(String json, String key, int searchFrom) {
        int idx = json.indexOf(key, searchFrom);
        if (idx == -1) return "";
        int colon = json.indexOf(':', idx + key.length());
        if (colon == -1) return "";
        int qStart = json.indexOf('"', colon + 1);
        if (qStart == -1) return "";
        int qEnd = json.indexOf('"', qStart + 1);
        if (qEnd == -1) return "";
        return json.substring(qStart + 1, qEnd);
    }

    private static String[] parseChatLines(String json) {
        int idx = json.indexOf("\"chat_lines\"");
        if (idx == -1) return new String[0];

        int arrStart = json.indexOf('[', idx);
        if (arrStart == -1) return new String[0];

        int arrEnd = json.indexOf(']', arrStart);
        if (arrEnd == -1) return new String[0];

        String arrContent = json.substring(arrStart + 1, arrEnd);
        if (arrContent.trim().isEmpty()) return new String[0];

        java.util.List<String> lines = new java.util.ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean inString = false;
        boolean escaped = false;

        for (int i = 0; i < arrContent.length(); i++) {
            char c = arrContent.charAt(i);

            if (escaped) {
                if (c == 'n') current.append('\n');
                else if (c == 't') current.append('\t');
                else if (c == 'u' && i + 4 < arrContent.length()) {
                    String hex = arrContent.substring(i + 1, i + 5);
                    try {
                        current.append((char) Integer.parseInt(hex, 16));
                        i += 4;
                    } catch (NumberFormatException e) {
                        current.append(c);
                    }
                } else {
                    current.append(c);
                }
                escaped = false;
            } else if (c == '\\' && inString) {
                escaped = true;
            } else if (c == '"') {
                inString = !inString;
            } else if (c == ',' && !inString) {
                lines.add(current.toString());
                current = new StringBuilder();
            } else if (inString) {
                current.append(c);
            }
        }
        if (current.length() > 0) {
            lines.add(current.toString());
        }

        return lines.toArray(new String[0]);
    }
}
