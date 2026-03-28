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

            // Write debug log to mods folder so we can see what happened
            if (modsDir != null) {
                log = new PrintWriter(new FileWriter(new File(modsDir.toFile(), "hypixelai-update.log"), true));
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
                if (log != null) { log.println("No .jar.update found, nothing to do"); log.println(); log.close(); }
                return;
            }
            if (updateFile.length() < 10000) {
                if (log != null) { log.println("Update file too small: " + updateFile.length() + " bytes, skipping"); log.println(); log.close(); }
                return;
            }

            if (log != null) log.println("Update file: " + updateFile.length() + " bytes");

            // 3. Remove ALL old hypixelai jars
            File[] oldJars = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && name.endsWith(".jar") && !name.endsWith(".jar.update"));
            if (oldJars != null) {
                for (File f : oldJars) {
                    if (f.delete()) {
                        String msg = "Deleted old jar: " + f.getName();
                        System.out.println("[HypixelAI] Pre-launch: " + msg);
                        if (log != null) log.println(msg);
                    } else {
                        File old = new File(f.getAbsolutePath() + ".old");
                        if (f.renameTo(old)) {
                            String msg = "Renamed " + f.getName() + " -> " + old.getName();
                            System.out.println("[HypixelAI] Pre-launch: " + msg);
                            if (log != null) log.println(msg);
                        } else {
                            String msg = "FAILED to remove " + f.getName() + " (canWrite=" + f.canWrite() + ", exists=" + f.exists() + ")";
                            System.out.println("[HypixelAI] Pre-launch: " + msg);
                            if (log != null) log.println(msg);
                        }
                    }
                }
            }

            // 4. Rename .jar.update -> .jar
            File target = new File(modsDir.toFile(), "hypixelai-mod.jar");
            if (updateFile.renameTo(target)) {
                String msg = "SUCCESS! Renamed .jar.update -> " + target.getName();
                System.out.println("[HypixelAI] Pre-launch: " + msg);
                if (log != null) log.println(msg);
            } else {
                try {
                    Files.move(updateFile.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
                    String msg = "SUCCESS (Files.move)! Applied update";
                    System.out.println("[HypixelAI] Pre-launch: " + msg);
                    if (log != null) log.println(msg);
                } catch (Exception ex) {
                    String msg = "FAILED: " + ex.getClass().getSimpleName() + " - " + ex.getMessage();
                    System.out.println("[HypixelAI] Pre-launch: " + msg);
                    if (log != null) log.println(msg);
                }
            }

            if (log != null) { log.println("Swap complete"); log.println(); }

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
}
