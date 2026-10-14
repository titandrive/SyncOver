#!/usr/bin/env python3
"""Build a standalone Morphe bundle. Requires JDK 21+ and Android SDK."""
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile
ROOT = Path(__file__).resolve().parent
BUILD = ROOT / 'build'
CACHE = Path(os.environ.get('SYNCOVER_BUILD_CACHE', str(ROOT / '.cache')))
JAVA_HOME = Path(os.environ.get('JAVA_HOME', '/opt/android-studio/jbr'))
SDK = Path(os.environ.get('ANDROID_HOME', str(Path.home() / 'Android/Sdk')))
def run(*args):
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT)
def fetch(name, url):
    dest = CACHE / name
    if not dest.exists():
        print('Downloading', name, flush=True)
        urllib.request.urlretrieve(url, dest.with_suffix('.download'))
        dest.with_suffix('.download').replace(dest)
    return dest
def archive(directory, output):
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in directory.rglob('*.class'): z.write(p, p.relative_to(directory))
def main():
    CACHE.mkdir(parents=True, exist_ok=True);BUILD.mkdir(exist_ok=True)
    morphe=fetch('morphe-desktop-1.18.0-all.jar','https://github.com/MorpheApp/morphe-desktop/releases/download/v1.18.0/morphe-desktop-1.18.0-all.jar')
    compiler=fetch('kotlin-compiler-embeddable-2.3.21.jar','https://repo.maven.apache.org/maven2/org/jetbrains/kotlin/kotlin-compiler-embeddable/2.3.21/kotlin-compiler-embeddable-2.3.21.jar')
    annotations=fetch('annotations-26.0.2.jar','https://repo.maven.apache.org/maven2/org/jetbrains/annotations/26.0.2/annotations-26.0.2.jar')
    java=JAVA_HOME/'bin/java'; javac=JAVA_HOME/'bin/javac'
    android=sorted((SDK/'platforms').glob('*/android.jar'))[-1]
    d8=sorted((SDK/'build-tools').glob('*/lib/d8.jar'))[-1]
    extension=BUILD/'extension';extension.mkdir(exist_ok=True)
    run(javac,'-source','8','-target','8','-classpath',android,'-d',extension,*sorted((ROOT/'src').rglob('*.java')))
    run(javac,'-classpath',extension,'-d',BUILD,ROOT/'tests/TrackerTest.java')
    run(java,'-cp',os.pathsep.join(map(str,(BUILD,extension))),'TrackerTest')
    extension_jar=BUILD/'extension.jar';archive(extension,extension_jar)
    dex=BUILD/'extension.zip'
    run(java,'-cp',d8,'com.android.tools.r8.D8','--release','--min-api','23','--lib',android,'--output',dex,extension_jar)
    classes=BUILD/'patches';classes.mkdir(exist_ok=True)
    cp=os.pathsep.join(map(str,(morphe,annotations)))
    run(java,'-cp',os.pathsep.join(map(str,(compiler,morphe,annotations))),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler',
        '-no-stdlib','-no-reflect','-classpath',cp,'-language-version','2.2','-jvm-target','11','-d',classes,ROOT/'patches/SyncErrorPatch.kt')
    patches_jar=BUILD/'patches.jar';archive(classes,patches_jar)
    patch_dex=BUILD/'patches.zip'
    run(java,'-cp',d8,'com.android.tools.r8.D8','--release','--min-api','26','--lib',android,'--classpath',morphe,'--output',patch_dex,patches_jar)
    bundle=BUILD/'syncover-android-0.1.0.mpp'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nName: SyncOver Android\nVersion: 0.1.0\nDescription: Syncthing-Fork sync-error notifications\nAuthor: titandrive\n\n')
        for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes))
        with zipfile.ZipFile(dex) as source:z.writestr('syncover/alerts.dex',source.read('classes.dex'))
        with zipfile.ZipFile(patch_dex) as source:
            for name in source.namelist():z.writestr(name,source.read(name))
    run(java,'-jar',morphe,'list-patches','--patches',bundle)
    print('Built',bundle,flush=True)
if __name__=='__main__':main()
