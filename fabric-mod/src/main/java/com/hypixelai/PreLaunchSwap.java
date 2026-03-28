package com.hypixelai;

import net.fabricmc.loader.api.entrypoint.PreLaunchEntrypoint;

import java.io.File;
import java.nio.file.*;

/**
 * Runs BEFORE Minecraft loads — swaps .jar.update to .jar before anything locks the file.
 * This is the only reliable way to auto-update on Windows.
 */
public class PreLaunchSwap implements PreLaunchEntrypoint {

    @Override
    public void onPreLaunch() {
        try {
            Path modsDir = findModsDir();
            if (modsDir == null) return;

            // 1. Delete any .disabled files from previous updates
            File[] disabled = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && name.contains("disabled"));
            if (disabled != null) {
                for (File f : disabled) {
                    f.delete();
                }
            }

            // 2. Check for pending update
            Path updateFile = modsDir.resolve("hypixelai-mod.jar.update");
            if (!Files.exists(updateFile) || Files.size(updateFile) < 10000) return;

            System.out.println("[HypixelAI] Pre-launch: applying update...");

            // 3. Find and delete/rename ALL old hypixelai jars
            File[] oldJars = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && name.endsWith(".jar") && !name.endsWith(".update"));
            if (oldJars != null) {
                for (File f : oldJars) {
                    if (!f.delete()) {
                        // Can't delete — rename to .disabled (will be cleaned next launch)
                        f.renameTo(new File(f.getAbsolutePath() + ".disabled"));
                    }
                    System.out.println("[HypixelAI] Pre-launch: removed " + f.getName());
                }
            }

            // 4. Rename .jar.update to .jar
            Path target = modsDir.resolve("hypixelai-mod.jar");
            Files.move(updateFile, target, StandardCopyOption.REPLACE_EXISTING);
            System.out.println("[HypixelAI] Pre-launch: update applied! New jar: " + target.getFileName());

        } catch (Exception e) {
            System.err.println("[HypixelAI] Pre-launch swap failed: " + e.getMessage());
        }
    }

    private static Path findModsDir() {
        // Try standard locations
        Path mods = Path.of("mods");
        if (Files.isDirectory(mods)) return mods;

        // Try from the class location
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
