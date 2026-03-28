package com.hypixelai;

import net.fabricmc.loader.api.entrypoint.PreLaunchEntrypoint;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.nio.file.*;
import java.time.LocalDateTime;

/**
 * Runs BEFORE Minecraft loads — swaps .jar.update to .jar.
 * Uses File.renameTo() which works better on Windows with locked files.
 */
public class PreLaunchSwap implements PreLaunchEntrypoint {

    @Override
    public void onPreLaunch() {
        PrintWriter log = null;
        try {
            Path modsDir = findModsDir();

            // Auto-configure PrismLauncher pre-launch command (one-time setup)
            setupPrismPreLaunch(modsDir);

            // Write debug log to .minecraft folder (NOT mods — Fabric tries to load everything in mods)
            File mcDir = modsDir != null ? modsDir.toFile().getParentFile() : null;
            if (mcDir != null) {
                log = new PrintWriter(new FileWriter(new File(mcDir, "hypixelai-update.log"), true));
                log.println("=== PreLaunch " + LocalDateTime.now() + " ===");
            }

            if (modsDir == null) {
                System.out.println("[HypixelAI] Pre-launch: could not find mods dir");
                return;
            }

            // List all hypixelai files
            File[] allFiles = modsDir.toFile().listFiles((dir, name) -> name.startsWith("hypixelai"));
            if (allFiles != null && log != null) {
                log.println("Files found:");
                for (File f : allFiles) {
                    log.println("  " + f.getName() + " (" + f.length() + " bytes, canWrite=" + f.canWrite() + ")");
                }
            }

            // 1. Delete old .disabled and .old files
            File[] oldStuff = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && (name.contains("disabled") || name.endsWith(".old")));
            if (oldStuff != null) {
                for (File f : oldStuff) {
                    boolean deleted = f.delete();
                    String msg = (deleted ? "Deleted " : "FAILED to delete ") + f.getName();
                    System.out.println("[HypixelAI] Pre-launch: " + msg);
                    if (log != null) log.println(msg);
                }
            }

            // 2. Check for pending update
            File updateFile = new File(modsDir.toFile(), "hypixelai-mod.jar.update");
            if (!updateFile.exists()) {
                File[] updateFiles = modsDir.toFile().listFiles((dir, name) ->
                        name.startsWith("hypixelai") && name.endsWith(".update"));
                if (updateFiles != null && updateFiles.length > 0) updateFile = updateFiles[0];
            }

            // 3. Check for swap script from previous shutdown hook (stored in .minecraft, not mods)
            File swapScript = new File(mcDir, "hypixelai-swap.cmd");
            if (swapScript.exists() && updateFile.exists()) {
                if (log != null) log.println("Running swap script before Fabric loads...");
                try {
                    // Run the swap script synchronously BEFORE Fabric locks anything
                    Process p = new ProcessBuilder("cmd.exe", "/c", swapScript.getAbsolutePath())
                            .directory(modsDir.toFile())
                            .redirectErrorStream(true)
                            .start();
                    p.waitFor(10, java.util.concurrent.TimeUnit.SECONDS);
                    if (log != null) log.println("Swap script finished, exit=" + p.exitValue());
                } catch (Exception ex) {
                    if (log != null) log.println("Swap script error: " + ex.getMessage());
                }
                // Refresh file state
                updateFile = new File(modsDir.toFile(), "hypixelai-mod.jar.update");
            }

            if (!updateFile.exists()) {
                if (log != null) { log.println("No .jar.update found, nothing to do"); log.println(); log.close(); }
                return;
            }
            if (updateFile.length() < 10000) {
                if (log != null) { log.println("Update too small: " + updateFile.length()); log.println(); log.close(); }
                return;
            }

            if (log != null) log.println("Update file: " + updateFile.length() + " bytes, trying direct swap...");

            // 4. Try direct swap (works if jar isn't locked yet)
            File[] oldJars = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && name.endsWith(".jar") && !name.endsWith(".jar.update"));
            if (oldJars != null) {
                for (File f : oldJars) {
                    if (f.delete()) {
                        if (log != null) log.println("Deleted: " + f.getName());
                    } else {
                        if (log != null) log.println("Locked: " + f.getName());
                    }
                }
            }

            File target = new File(modsDir.toFile(), "hypixelai-mod.jar");
            if (!target.exists()) {
                if (updateFile.renameTo(target)) {
                    if (log != null) log.println("SUCCESS! Update applied");
                } else {
                    if (log != null) log.println("Rename failed");
                }
            } else {
                if (log != null) log.println("Old jar still locked, will retry via shutdown hook");
            }

            if (log != null) { log.println("PreLaunch done"); log.println(); }

        } catch (Exception e) {
            System.err.println("[HypixelAI] Pre-launch error: " + e.getMessage());
            e.printStackTrace();
            if (log != null) { log.println("ERROR: " + e.getMessage()); log.println(); }
        } finally {
            if (log != null) log.close();
        }
    }

    private static Path findModsDir() {
        // First: try from the jar's own location (most reliable — works with all launchers)
        try {
            Path jar = Path.of(PreLaunchSwap.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI());
            if (jar.toString().endsWith(".jar") && jar.getParent() != null) {
                System.out.println("[HypixelAI] Pre-launch: mods dir from jar location: " + jar.getParent());
                return jar.getParent();
            }
        } catch (Exception ignored) {}

        // Fallback: relative path (works when CWD is .minecraft)
        Path mods = Path.of("mods");
        if (Files.isDirectory(mods)) {
            System.out.println("[HypixelAI] Pre-launch: mods dir from CWD: " + mods.toAbsolutePath());
            return mods;
        }

        // Fallback: Fabric loader knows the game dir
        try {
            Path gameDir = net.fabricmc.loader.api.FabricLoader.getInstance().getGameDir();
            Path fabricMods = gameDir.resolve("mods");
            if (Files.isDirectory(fabricMods)) {
                System.out.println("[HypixelAI] Pre-launch: mods dir from Fabric: " + fabricMods);
                return fabricMods;
            }
        } catch (Exception ignored) {}

        System.out.println("[HypixelAI] Pre-launch: could not find mods dir anywhere");
        return null;
    }

    /**
     * Auto-configure PrismLauncher to run a pre-launch command that swaps jars
     * BEFORE Java starts. This is the only reliable way on Windows.
     * Also works with MultiMC (same config format).
     */
    private static void setupPrismPreLaunch(Path modsDir) {
        if (modsDir == null) return;
        try {
            // Walk up from mods/ -> .minecraft/ -> instance dir to find instance.cfg
            Path mcDir = modsDir.getParent(); // .minecraft
            if (mcDir == null) return;
            Path instanceDir = mcDir.getParent(); // instance root
            if (instanceDir == null) return;

            File instanceCfg = new File(instanceDir.toFile(), "instance.cfg");
            if (!instanceCfg.exists()) return; // Not PrismLauncher/MultiMC

            // Read current config
            String config = new String(java.nio.file.Files.readAllBytes(instanceCfg.toPath()), java.nio.charset.StandardCharsets.UTF_8);

            // Check if we already configured it
            if (config.contains("hypixelai-mod.jar.update")) {
                System.out.println("[HypixelAI] Pre-launch: PrismLauncher already configured");
                return;
            }

            // Build the pre-launch command
            String cmd = "cmd /c \"cd /d \\\"$INST_MC_DIR\\mods\\\" && if exist hypixelai-mod.jar.update (for %%f in (hypixelai-mod*.jar) do del /f /q \\\"%%f\\\" 2>nul & ren \\\"hypixelai-mod.jar.update\\\" \\\"hypixelai-mod.jar\\\")\"";

            // Update config
            config = config.replace("OverrideCommands=false", "OverrideCommands=true");
            config = config.replace("PreLaunchCommand=", "PreLaunchCommand=" + cmd);

            java.nio.file.Files.writeString(instanceCfg.toPath(), config, java.nio.charset.StandardCharsets.UTF_8);
            System.out.println("[HypixelAI] Pre-launch: Configured PrismLauncher pre-launch command automatically!");

        } catch (Exception e) {
            System.out.println("[HypixelAI] Pre-launch: Could not configure PrismLauncher: " + e.getMessage());
        }
    }
}
