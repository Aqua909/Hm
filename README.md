# ManhwaUpdatesBot

## About:

This is a bot that will periodically check for updates on the manga that you have subscribed to and alert you when there is a new chapter available.

## Requirements:

- Python 3.10+

This bot currently only supports the following websites:

- https://toonily.com
- https://manganato.com (alternatively known as https://chapmanganato.com)
- https://tritinia.org
- https://mangadex.org
- https://flamescans.org
- https://asurascans.com
- https://reaperscans.com
- https://anigliscans.com

Note: More websites will be added in the future, but only if I have some manga on it that I am reading, so don't hope for too much.
Additionally, websites that are heavily protected by Cloudflare will also not be added (I will list the ones I tried to 
add that fit these criteria at the bottom of this file).

If you want to leave a suggesting of a website that I should implement for this, send me a DM over on Mooshi#6669 on discord!
Or you can contact me through my email at rchiriac16@gmail.com

### If you want to invite the bot to your server, click [here.](https://discord.com/api/oauth2/authorize?client_id=1031998059447590955&permissions=412854111296&scope=bot%20applications.commands)
  
How to set up the bot:

1. Cloning the repository

   ```bash
   git clone https://github.com/MooshiMochi/ManhwaUpdatesBot
   cd ManhwaUpdatesBot
   ```

2. Running the bot
   **windows:**

   ```bash
   .\run.bat
   ```

   **linux:**

   ```bash
   chmod +x run.sh setup.sh
   ./run.sh
   ```


## Todo:
   ### Websites to add: 
      en.leviathanscans.com
      luminousscans.com (maybe)
      void-scans.com
      drakescans.com
      nitroscans.com

   ### Cloudflare protected websites to add:
      Nothing at the moment...

   ### Features to add:
      - a bookmark feature where the user can bookmark both a completed manga and an ongoing manga
      the user will be able to edit the chapter that they've read for each bookmarked manga.
      This will most likely be done through a view.
      Note: for this to work, the auto delete feature of series from database will need to be removed.

      - a command that will show the user all the manga that they have bookmarked

      - When a series has been marked complete/dropped, send a notification in the updates
      channel that the series has been marked as such.

   ### Issues:
      - Rearrange the function order in each of the scanlators.py classes to follow that of the
      ABCScan class

      - Create a .sh file that will configure the system for pypetteer.

      - aquamanga.org is not working on Linux. it returns 5001 error with text "enable cookies"


## Contributing:
   ```
   If you want to contribute to this project, feel free to fork the repository and make a pull request.
   I will review the changes and merge them if they are good.
   ``` 

### Websites heavily protected by Cloudflare (won't be considered for this project)
   ```
   https://aquamanga.com
   ```
