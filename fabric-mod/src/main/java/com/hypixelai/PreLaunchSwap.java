package com.hypixelai;

import net.fabricmc.loader.api.entrypoint.PreLaunchEntrypoint;
import java.io.File;
import java.nio.file.*;

/**
 * PreLaunch — just cleans up leftover files from previous updates.
 * The actual jar swap is handled by a PowerShell process spawned by the updater.
 */
public class PreLaunchSwap implements PreLaunchEntrypoint {

    @Override
    public void onPreLaunch() {
        try {
            Path modsDir = findModsDir();
            if (modsDir == null) return;

            // Clean up .old, .disabled files from previous updates
            File[] leftovers = modsDir.toFile().listFiles((dir, name) ->
                    name.startsWith("hypixelai") && (name.endsWith(".old") || name.endsWith(".disabled")));
            if (leftovers != null) {
                for (File f : leftovers) f.delete();
            }
        } catch (Exception ignored) {}
    }

    private static Path findModsDir() {
        try {
            Path jar = Path.of(PreLaunchSwap.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI());
            if (jar.toString().endsWith(".jar") && jar.getParent() != null) return jar.getParent();
        } catch (Exception ignored) {}
        Path mods = Path.of("mods");
        if (Files.isDirectory(mods)) return mods;
        return null;
    }
}
