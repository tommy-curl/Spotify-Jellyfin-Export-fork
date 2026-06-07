import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
import os
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import requests
import logging
import time
import pickle
import hashlib
import json

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

load_dotenv()
if not os.getenv("SPOTIPY_CLIENT_ID") or not os.getenv("SPOTIPY_CLIENT_SECRET") or not os.getenv("SPOTIPY_REDIRECT_URI"):
    print("please populate .env file", file=sys.stderr)
    exit()

# wrapper-function for api-requests and logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def _cache_key(func_name, args, kwargs):
    raw = {
        "func": func_name,
        "args": args,
        "kwargs": kwargs
    }
    encoded = json.dumps(raw, sort_keys=True, default=str).encode()
    return hashlib.md5(encoded).hexdigest()


def cached_api_call(api_func, *args, **kwargs):
    key = _cache_key(api_func.__name__, args, kwargs)
    path = os.path.join(CACHE_DIR, f"{key}.pkl")

    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)

    result = cached_api_call(api_func, *args, **kwargs)

    with open(path, "wb") as f:
        pickle.dump(result, f)

    return result

def cached_api_call(api_func, *args, **kwargs):
    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=1, min=30, max=300),
        retry=retry_if_exception_type((SpotifyException, requests.exceptions.Timeout)),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _execute():
        time.sleep(0.5) # sleep 0.5 seconds to not exceed api-rate-limits as quickly
                        # https://developer.spotify.com/documentation/web-api/concepts/rate-limits
                        # 'rolling 30-second window' => max 60 requests in window, should be fine-ish?
                        # internet claims 100 per frame, but lower limits for certain endpoints(?)
        return api_func(*args, **kwargs)


    return _execute()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv("SPOTIPY_CLIENT_ID"),
                                               client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
                                               redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
                                               scope="user-library-read playlist-read-private user-follow-read"))

# global variable for later export
albums = {}

playlists = {}
print("fetching playlistIDs ...")
total_playlists = (int)(cached_api_call(sp.current_user_playlists,limit=50, offset=0)['total'])
print(f"    total: {total_playlists}")
playlistsIDs = []
for x in range(0,total_playlists,50):
    playlistsIDs += cached_api_call(sp.current_user_playlists,limit=50, offset=x)['items']

print("fetching playlist contents ...")
for i, playlist in enumerate(playlistsIDs):
    basicData = cached_api_call(sp.playlist,playlist['id'])

    allSongs = []
    if 'items' in basicData:
        allSongs = [record['item'] for record in basicData['items']['items']]
        if basicData['items']['total'] > 100:
            for x in range(100, basicData['items']['total'], 50):
                allSongs += [record['item'] for record in cached_api_call(sp.playlist_items, playlist['id'], offset=x)['items']]
    else:
        # collaborative playlists don't allow for fetching the song list if not collaborator; skipping these
        # with funky logic, bc for whatever reason in testing the API returned "collaborative=False" for playlists
        # that were collaborative; *sigh*
        print(f"    ({i+1}/{total_playlists}) {playlist['id']} ... has no items property; skipping  '{playlist['name']}' ({playlist['external_urls']['spotify']})")
        continue

    playlists[playlist['id']] = {
        "name" : playlist['name'],
        "creator" : playlist['owner']['display_name'],
        "creator_profile" : playlist['owner']['external_urls']['spotify'],
        "songs": allSongs
    }

    print(f"    ({i+1}/{total_playlists}) {playlist['id']} ... done")

likedSongs = cached_api_call(sp.current_user_saved_tracks, limit=50)
allLikedSongs = [record['track'] for record in likedSongs['items']]
if likedSongs['total'] > 100:
    for x in range(50, likedSongs['total'], 50):
        allLikedSongs += [record['track'] for record in cached_api_call(sp.current_user_saved_tracks, offset=x, limit=50)['items']]
playlists['likedSongs'] = {
    "name": "liked songs",
    "songs": allLikedSongs
}

for playlist in playlists:
    for song in playlists[playlist]['songs']:
        if song is None:
            print(f"Skipping invalid track in playlist '{playlist}'")
            continue

        album = song.get('album')
        if album is None:
            print(f"Skipping track without album in playlist '{playlist}'")
            continue

        album_id = album.get('id')
        if album_id is None:
            print(f"Skipping album without ID in playlist '{playlist}'")
            continue

        if album_id not in albums:
            artists = {}
            for artist in album.get('artists', []):
                if artist and artist.get('id'):
                    artists[artist['id']] = {
                        "name": artist['name'],
                        "id": artist['id']
                    }

            if len(album.get('images', [])) == 0:
                url = ""
            else:
                url = album['images'][0]['url']

            albums[album_id] = {
                "name": album['name'],
                "artists": artists,
                "release": album['release_date'],
                "image": url
            }

print("fetching followed artists ...")
totalArtists = (cached_api_call(sp.current_user_followed_artists, limit=20, after=None)['artists']['total'])
artists = []
for x in range(0,totalArtists,20):
    print(f"    ({x}/{totalArtists})")
    artists += cached_api_call(sp.current_user_followed_artists, limit=20, after=x)['artists']['items']
print(f"    ({totalArtists}/{totalArtists})")

print("fetching artists albums")
i = 1
total = len(artists)
for artist in artists:
    time.sleep(0.5)
    print(f"    ({i}/{total}) {artist['name']}")
    i=i+1
    req = cached_api_call(sp.artist_albums, artist['id'], limit=10, include_groups='album, single, compilation')
    artistAlbums = req['items']
    if req['total'] > 10:
        totalAlbums = req['total']
        currentLimit = req['limit']
        for x in range(currentLimit, totalAlbums, currentLimit):
            artistAlbums += [album for album in cached_api_call(sp.artist_albums, artist['id'], offset=x, limit=10, include_groups='album, single, compilation')['items']]
    for album in artistAlbums:
        if not album['id'] in albums:
            artists = {}
            for artist in album['artists']:
                artists[artist['id']] = {
                    "name": artist['name'],
                    "id": artist['id']
                }
            albums[album['id']] = {
                "name": album['name'],
                "artists": artists,
                "release": album['release_date'],
                "trackCount": album['total_tracks'],
                "cover": album['images'][0]['url']
            }


print("pickling Data")
os.makedirs("pickle", exist_ok=True)

with open('pickle/albums.pickle', 'wb') as handle:
    pickle.dump(albums, handle, protocol=pickle.HIGHEST_PROTOCOL)

with open('pickle/playlists.pickle', 'wb') as handle:
    pickle.dump(playlists, handle, protocol=pickle.HIGHEST_PROTOCOL)

with open('pickle/artists.pickle', 'wb') as handle:
    pickle.dump(artists, handle, protocol=pickle.HIGHEST_PROTOCOL)