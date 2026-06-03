import sys
import os
import eyed3

if len(sys.argv) < 2:
    print("Bitte Pfad mit Musikdateien angeben")

fullPath = sys.argv[1]

if not os.path.exists(fullPath):
    print(f"Ungültiger Pfad: {fullPath}")

files = os.listdir(fullPath)

for file in files:
    if os.path.isdir(fullPath+file):
        print(f"{fullPath+file} is dir; skipping")
        continue

    tags = eyed3.load(fullPath+file)

    if tags is None:
        continue

    if not os.path.exists(fullPath+tags.tag.album_artist):
        os.makedirs(fullPath+tags.tag.album_artist)
    if not os.path.exists(fullPath+tags.tag.album_artist+"/"+tags.tag.album):
        os.makedirs(fullPath+tags.tag.album_artist+"/"+tags.tag.album)

    os.rename(fullPath+file, fullPath+tags.tag.album_artist+"/"+tags.tag.album+"/"+file)

print("done")