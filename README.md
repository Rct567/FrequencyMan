# FrequencyMan (Anki Plugin)

## Overview
FrequencyMan is an Anki plugin designed to help you sort your cards based on word frequency. 

Please not that this plugin is a __WORK IN PROGRESS__. Don't use it on your main profile!

## Installation

1. Open to the Anki plugin folder, such as __C:\Users\%USERNAME%\AppData\Roaming\Anki2\addons21__
2. Create a new folder for the plugin, such as addons21\FrequencyMan
3. Clone the project in the new folder: `git clone https://github.com/Rct567/FrequencyMan.git`
4. Place your word frequency list files on subfolder \FrequencyMan\user_files\frequency_lists\en
5. Start Anki.

## Usage
FrequencyMan allows you to sort your cards based on word frequency. Here's how to use it:

1. Open the "FrequencyMan" menu option in the "Tools" menu of the main Anki window.
2. This will open the "FrequencyMan Main Window" where you can define your sorting targets.
3. Define your sorting targets using JSON data. Ensure the data is in the correct format.
4. Click the "Reorder Cards" button to apply the sorting.
5. FrequencyMan will sort your cards based on the word frequency from word frequency lists.

## Features
- Sort cards based on word frequency.
- Define multiple sorting targets for different collection/decks of cards.
- Can use multiple field (such as 'front' __and__ 'back') to calculate the ranking.
- Each field has its language and multiple word frequency list files can be used per language.