import sys
import os
import re
import json
import numpy as np
from datetime import datetime
import pickle
import csv

# Constants
SCORE_EXPONENT = 2.3
SCORE_DIVISOR = 10
SPOTIFY_EPOCH = datetime(2008, 10, 1, 0, 0)
FILE_PATTERN = r"Streaming_History_Audio_\d{4}(_\d+|).json"

def write_csv(filename, headers, data):
    """Helper function to write CSV files consistently"""
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)

if len(sys.argv) < 2:
    print("Bitte Pfad zu dekomprimierter extended Streaming History")
    sys.exit(1)

fullPath = sys.argv[1] + "/Spotify Extended Streaming History/"

if not os.path.exists(fullPath):
    print(f"Ungültiger Pfad: {fullPath}")
    sys.exit(1)

files = os.listdir(fullPath)
fileNameRegEx = re.compile(FILE_PATTERN)

# Calculate timestamps
nowUnixTime = datetime.now().timestamp()
spotUnixTime = SPOTIFY_EPOCH.timestamp()

albumPrioList = {}

for file in files:
    if fileNameRegEx.match(file):
        print(f"reading file {file}")
        with open(fullPath + file, 'r') as f:
            data = json.load(f)
            for entry in data:
                streamTime = datetime.fromisoformat(entry['ts'])
                streamTimeTS = streamTime.timestamp()

                score = (np.exp(SCORE_EXPONENT * ((streamTimeTS - spotUnixTime) / (nowUnixTime - spotUnixTime)))) / SCORE_DIVISOR

                artist = entry.get('master_metadata_album_artist_name')
                album = entry.get('master_metadata_album_album_name')

                if artist is None or album is None:
                    continue

                if artist not in albumPrioList:
                    albumPrioList[artist] = {}
                if album not in albumPrioList[artist]:
                    albumPrioList[artist][album] = score
                else:
                    albumPrioList[artist][album] += score
    else:
        print(f"file name {file} didn't match regex; skipping")

# Save streaming history pickle
with open('pickle/streamingHistory.pickle', 'wb') as handle:
    pickle.dump(albumPrioList, handle, protocol=pickle.HIGHEST_PROTOCOL)

# Create streaming shortlist
streamingShortList = [
    {"artist": artist, "album": album, "score": score}
    for artist, albums in albumPrioList.items()
    for album, score in albums.items()
]

# Write albumPrioList.csv
write_csv("albumPrioList.csv", ["artist", "album", "score"],
          sorted(streamingShortList, key=lambda x: x["score"], reverse=True))

# Create artist-sorted view
sortedByArtist = dict(
    sorted(albumPrioList.items(), key=lambda item: sum(item[1].values()), reverse=True)
)

# Write artistPrioList.csv
with open('artistPrioList.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['artist', 'album', 'album score'])
    for artist, albums in sortedByArtist.items():
        sortedAlbums = sorted(albums.items(), key=lambda x: x[1], reverse=True)
        for albumName, score in sortedAlbums:
            writer.writerow([artist, albumName, score])

# Write artists.csv
with open('artists.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    for artist in sortedByArtist.keys():
        writer.writerow([artist])

# Process playlists
try:
    with open("pickle/playlists.pickle", 'rb') as picklefile:
        playlists = pickle.load(picklefile)
except FileNotFoundError:
    print("Warning: playlists.pickle not found. Skipping playlist processing.")
    playlists = {}

playlistList = {}
for playlist, data in playlists.items():
    for song in data.get('songs', []):
        try:
            artist = song['album']['artists'][0]['name']
            album = song['album']['name']

            if artist not in playlistList:
                playlistList[artist] = {}
            if album not in playlistList[artist]:
                playlistList[artist][album] = 1  # FIX: Start at 1, not 0
            else:
                playlistList[artist][album] += 1
        except (KeyError, IndexError):
            continue  # Skip malformed songs

# Create playlist shortlist (FIXED: append to correct list)
playlistShortlist = [
    {"artist": artist, "album": album, "score": count}
    for artist, albums in playlistList.items()
    for album, count in albums.items()
]

# Write playlistPrioList.csv
write_csv("playlistPrioList.csv", ["artist", "album", "score"],
          sorted(playlistShortlist, key=lambda x: x["score"], reverse=True))

# Create playlistByStream with streaming scores
playlistByStream = []
for entry in playlistShortlist:
    artist = entry['artist']
    album = entry['album']

    streamScore = albumPrioList.get(artist, {}).get(album, 0)
    playlistByStream.append({
        "artist": artist,
        "album": album,
        "score": streamScore
    })

# Write playlistByStream.csv
write_csv("playlistByStream.csv", ["artist", "album", "score"],
          sorted(playlistByStream, key=lambda x: x["score"], reverse=True))