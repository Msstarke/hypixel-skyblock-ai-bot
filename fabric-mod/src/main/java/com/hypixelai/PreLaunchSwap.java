package com.hypixelai;

import net.fabricmc.loader.api.entrypoint.PreLaunchEntrypoint;

import java.io.File;
import java.nio.file.*;

/**
 * Runs BEFORE Minecraft loads — swaps .jar.update to .jar.
 * Uses File.renameTo() which works better on Windows with locked files.
 */
public class PreLaunchSwap implements PreLaunchEntrypoint {

    @Override
    public void onPreLaunch() {
        try {
            Path modsDir = findModsDir();
            if (modsDir == null) {
                System.out.println("[HypixelAI] Pre-launch: could not find mods dir");
                return;
            }

            // 1. Delete old .disabled files
            File[] disabled = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && name.contains("disabled"));
            if (disabled != null) {
                for (File f : disabled) {
                    if (f.delete()) {
                        System.out.println("[HypixelAI] Pre-launch: deleted " + f.getName());
                    }
                }
            }

            // 2. Check for pending update
            File updateFile = new File(modsDir.toFile(), "hypixelai-mod.jar.update");
            if (!updateFile.exists() || updateFile.length() < 10000) {
                return;
            }

            System.out.println("[HypixelAI] Pre-launch: found update (" + updateFile.length() + " bytes), applying...");

            // 3. Remove ALL old hypixelai jars
            File[] oldJars = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && name.endsWith(".jar") && !name.endsWith(".jar.update"));
            if (oldJars != null) {
                for (File f : oldJars) {
                    // Try delete first
                    if (f.delete()) {
                        System.out.println("[HypixelAI] Pre-launch: deleted " + f.getName());
                    } else {
                        // Can't delete — rename to .old (different extension so Fabric ignores it)
                        File old = new File(f.getAbsolutePath() + ".old");
                        if (f.renameTo(old)) {
                            System.out.println("[HypixelAI] Pre-launch: renamed " + f.getName() + " -> " + old.getName());
                        } else {
                            System.out.println("[HypixelAI] Pre-launch: WARNING could not remove " + f.getName());
                        }
                    }
                }
            }

            // 4. Rename .jar.update -> .jar
            File target = new File(modsDir.toFile(), "hypixelai-mod.jar");
            if (updateFile.renameTo(target)) {
                System.out.println("[HypixelAI] Pre-launch: SUCCESS! Update applied -> " + target.getName());
            } else {
                // Try Files.move as fallback
                try {
                    Files.move(updateFile.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
                    System.out.println("[HypixelAI] Pre-launch: SUCCESS (Files.move)! Update applied -> " + target.getName());
                } catch (Exception ex) {
                    System.out.println("[HypixelAI] Pre-launch: FAILED to apply update: " + ex.getMessage());
                }
            }

            // 5. Clean up any .old files that we can now delete
            File[] oldFiles = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && name.endsWith(".old"));
            if (oldFiles != null) {
                for (File f : oldFiles) {
                    f.delete(); // best effort
                }
            }

        } catch (Exception e) {
            System.err.println("[HypixelAI] Pre-launch error: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private static Path findModsDir() {
        // Standard location
        Path mods = Path.of("mods");
        if (Files.isDirectory(mods)) return mods;

        // From class location
        try {
            Path jar = Path.of(PreLaunchSwap.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI());
            if (jar.toString().endsWith(".jar") && jar.getParent() != null) {
                return jar.getParent();
            }
        } catch (Exception ignored) {}

        return null;
    }
}
