#!/usr/bin/env bash
set -e

GRADLE_VERSION="8.2"
GRADLE_DIR="/tmp/gradle-${GRADLE_VERSION}"

if [ ! -d "${GRADLE_DIR}" ]; then
    echo ">>> Downloading Gradle ${GRADLE_VERSION}..."
    wget -q "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -O /tmp/gradle-bin.zip
    unzip -q /tmp/gradle-bin.zip -d /tmp/
    rm -f /tmp/gradle-bin.zip
fi

export PATH="${GRADLE_DIR}/bin:$PATH"
echo ">>> Gradle version:"
gradle --version

cd /workspace/android_sensor_agent

echo ">>> Building Android Sensor Agent APK..."
gradle assembleDebug --no-daemon
echo ">>> Build completed successfully!"
ls -la app/build/outputs/apk/debug/
