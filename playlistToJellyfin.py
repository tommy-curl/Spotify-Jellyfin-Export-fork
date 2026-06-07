import pickle
import os
import sys
import requests
import re
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("JELLYFIN_URL") or not os.getenv("JELLYFIN_API_KEY") or not os.getenv("JELLYFIN_USER_ID"):
    print("please populate .env file", file=sys.stderr)
    exit()

jellyfinHeaders = {
    "X-Emby-Token": os.getenv("JELLYFIN_API_KEY"),
    "Content-Type": "application/json"
}
try:
    response = requests.get(f"{os.getenv('JELLYFIN_URL')}/System/Info", headers=jellyfinHeaders)
    response.raise_for_status()

except exception as e:
    print(f"Jellyfin Connection Failed: {e}")
    exit(1)

def normalize(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())

try:
    with open("pickle/playlists.pickle", 'rb') as picklefile:
        playlists = pickle.load(picklefile)
except:
    print("could not unpickle playlists.pickle")
    exit(1)

idAndNames = {outerKey: innerDict['name'] for outerKey, innerDict in playlists.items()}
idAndNamesSorted = dict(sorted(idAndNames.items(), key=lambda x: x[1].lower()))
print("Available Playlists:")
for id, playlist in idAndNamesSorted.items():
    if id == 'likedSongs':
        continue
    print(f"{id}      {playlist}")

id = input("enter an id: ")

if not id in playlists:
    print("Invalid id")
    exit(1)

# fetch music library from jellyfin
try:
    response = requests.get(os.getenv("JELLYFIN_URL")+"/Items", headers=jellyfinHeaders, params={
        "IncludeItemTypes": "Audio",
        "Recursive": "true"
    })
    response.raise_for_status()
    responseJSON = response.json()
    allSongs = responseJSON['Items']
except exception as e:
    print(f"jellyfin query failed: {e}")

jellyfinIDs = []
for song in playlists[id]['songs']:
    normTitle = normalize(song['name'])
    normArtist = normalize(song['artists'][0]['name'])

    bestMatch = {
        'id': '',
        'score': 0.0,
        'song': {}
    }

    exactMatch = False

    for librarySong in allSongs:
        libTitle = normalize(librarySong['Name'])
        libArtists = [normalize(a) for a in librarySong['Artists']]

        #check exact match
        if normTitle == libTitle and normArtist in libArtists:
            jellyfinIDs.append(librarySong['Id'])
            exactMatch = True
            break

        titleSimilarity = SequenceMatcher(None, normTitle, libTitle).ratio()
        highestArtistSimilarity = 0
        for libArtist in libArtists:
            ratio = SequenceMatcher(None, normArtist, libArtist).ratio()
            if ratio > highestArtistSimilarity:
                highestArtistSimilarity = ratio

        combinedScore = (titleSimilarity + highestArtistSimilarity) / 2
        if combinedScore > bestMatch['score']:
            bestMatch['score'] = combinedScore
            bestMatch['id'] = librarySong['Id']
            bestMatch['song'] = librarySong

    if exactMatch:
        continue

    if bestMatch['score'] > 0.85:
        print(f"no exact match for {song['name']} by {song['artists'][0]['name']}")
        print(f"Best Candidate (Score: {bestMatch['score']*100}%): {bestMatch['song']['Name']} by {bestMatch['song']['Artists']}")
        choice = ''
        while choice!='y' and choice!='n':
            choice = input("accept? (y/n)")
        if choice == 'y':
            jellyfinIDs.append(bestMatch['song']['Id'])
    else:
        print(f"no exact or fuzzy match for {song['name']} by {song['artists'][0]['name']}")


# import playlist
if len(jellyfinIDs) > 0:
    payload = {
        "Name": playlists[id]['name'],
        "Ids": jellyfinIDs,
        "UserId": os.getenv("JELLYFIN_USER_ID")
    }

    try:
        response = requests.post(os.getenv("JELLYFIN_URL")+"/Playlists", json=payload, headers=jellyfinHeaders)
        response.raise_for_status()
        responseJSON = response.json()
        print(f"Created Playlist {responseJSON['Id']}: {playlists[id]['name']}")
    except exception as e:
        print(f"jellyfin playlist creation failed: {e}")
else:
    print("no songs found in jellyfin; not creating playlist")
