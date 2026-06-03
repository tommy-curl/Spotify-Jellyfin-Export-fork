# Export Data
[Doku](https://spotipy.readthedocs.io/en/2.26.0/)
1) App im [spotify developer dashboard](https://developer.spotify.com/dashboard) einrichten
2) Client ID und Secret in .env hinterlegen
3)
```bash
python3.12 -m venv ./ --system-site-packages
source bin/activate
pip install spotipy python-dotenv numpy eyed3 tenacity requests
python3.12 main.py
```

# Scripte

| Name               | Beschreibung | Usage |
|--------------------| --- | --- |
| id3ToJellyfin      | Sehr simples script, das einen Ordner voller getaggter mp3 in eine Ordner Struktur `Artist/Album/` verwandelt. | `python3 id3ToJellyfin.py /path/to/folder` |
| playlistToJellyfin | Importiert eine Spotify Playlist in Jellyfin. Funktioniert nur nachdem spotifyAPIExporter ausgeführt wurde. | `python3 playlistToJellyfin.py`|
| prioListGenerator | Erstellt Listen zur Priorisierung der Reihenfolge der Albumbeschaffung anhand der Stremainghistory und Playlists | `python3 prioListGenerator.py /path/to/streamingHistoryUnziped`|
| spotifyAPIExporter | Exportiert verschiedene Daten aus der Spotify API und legt diese in pickles ab, um sie anderen Scripten zugängig zu machen | `python3 spotifyAPIExporter.py`|

# Disclaimer
Sorry für die katastophale Code-Qualität :D