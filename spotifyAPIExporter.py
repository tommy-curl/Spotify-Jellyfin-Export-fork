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

def api_call(api_func, *args, **kwargs):
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
total_playlists = (int)(api_call(sp.current_user_playlists,limit=50, offset=0)['total'])
print(f"    total: {total_playlists}")
playlistsIDs = []
for x in range(0,total_playlists,50):
    playlistsIDs += api_call(sp.current_user_playlists,limit=50, offset=x)['items']

print("fetching playlist contents ...")
for i, playlist in enumerate(playlistsIDs):
    basicData = api_call(sp.playlist,playlist['id'])

    allSongs = []
    if 'items' in basicData:
        allSongs = [record['item'] for record in basicData['items']['items']]
        if basicData['items']['total'] > 100:
            for x in range(100, basicData['items']['total'], 50):
                allSongs += [record['item'] for record in api_call(sp.playlist_items, playlist['id'], offset=x)['items']]
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

likedSongs = api_call(sp.current_user_saved_tracks, limit=50)
allLikedSongs = [record['track'] for record in likedSongs['items']]
if likedSongs['total'] > 100:
    for x in range(50, likedSongs['total'], 50):
        allLikedSongs += [record['track'] for record in api_call(sp.current_user_saved_tracks, offset=x, limit=50)['items']]
playlists['likedSongs'] = {
    "name": "liked songs",
    "songs": allLikedSongs
}

for playlist in playlists:
    for song in playlists[playlist]['songs']:
        if not song['album']['id'] in albums:
            artists = {}
            for artist in song['album']['artists']:
                artists[artist['id']] = {
                    "name": artist['name'],
                    "id": artist['id']
                }
            if len(song['album']['images']) == 0:
                url = ""
            else:
                url = song['album']['images'][0]['url']
            albums[song['album']['id']] = {
                "name": song['album']['name'],
                "artists": artists,
                "release": song['album']['release_date'],
                "trackCount": song['album']['total_tracks'],
                "cover": url,
                "count": 1
            }
        else:
            albums[song['album']['id']]['count'] = albums[song['album']['id']]['count']+1

print("fetching liked albums ...")
totalLikedAlbums = (int)(api_call(sp.current_user_saved_albums,limit=50, offset=0)['total'])
likedAlbums = []
for x in range(0,totalLikedAlbums,50):
    likedAlbums += api_call(sp.current_user_saved_albums, limit=50, offset=x)['items']
    print(f"    ({x}/{totalLikedAlbums})")
print(f"    ({totalLikedAlbums}/{totalLikedAlbums})")

for album in likedAlbums:
    if not album['album']['id'] in albums or 'songs' not in albums[album['album']['id']]:
        artists = {}
        for artist in album['album']['artists']:
            artists[artist['id']] = {
                "name": artist['name'],
                "id": artist['id']
            }
        albums[album['album']['id']] = {
            "name": album['album']['name'],
            "artists": artists,
            "release": album['album']['release_date'],
            "trackCount": album['album']['total_tracks'],
            "cover": album['album']['images'][0]['url']
        }

print("fetching followed artists ...")
totalArtists = (api_call(sp.current_user_followed_artists, limit=20, after=None)['artists']['total'])
artists = []
for x in range(0,totalArtists,20):
    print(f"    ({x}/{totalArtists})")
    artists += api_call(sp.current_user_followed_artists, limit=20, after=x)['artists']['items']
print(f"    ({totalArtists}/{totalArtists})")

print("fetching artists albums")
i = 1
total = len(artists)
for artist in artists:
    time.sleep(0.5)
    print(f"    ({i}/{total}) {artist['name']}")
    i=i+1
    req = api_call(sp.artist_albums, artist['id'], limit=10, include_groups='album, single, compilation')
    artistAlbums = req['items']
    if req['total'] > 10:
        totalAlbums = req['total']
        currentLimit = req['limit']
        for x in range(currentLimit, totalAlbums, currentLimit):
            artistAlbums += [album for album in api_call(sp.artist_albums, artist['id'], offset=x, limit=10, include_groups='album, single, compilation')['items']]
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

with open('pickle/albums.pickle', 'wb') as handle:
    pickle.dump(albums, handle, protocol=pickle.HIGHEST_PROTOCOL)

with open('pickle/likedAlbums.pickle', 'wb') as handle:
    pickle.dump(likedAlbums, handle, protocol=pickle.HIGHEST_PROTOCOL)

with open('pickle/playlists.pickle', 'wb') as handle:
    pickle.dump(playlists, handle, protocol=pickle.HIGHEST_PROTOCOL)

with open('pickle/artists.pickle', 'wb') as handle:
    pickle.dump(artists, handle, protocol=pickle.HIGHEST_PROTOCOL)