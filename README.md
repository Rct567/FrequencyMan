# FrequencyMan (Anki Plugin)

## Overview

As an Anki plugin, __FrequencyMan__ goal is to optimize your Anki learning journey by allowing you to intelligently __sort your new cards__.

Please note: this plugin is a __WORK IN PROGRESS__. Don't use it on your main profile!

## Features
- Sort cards based on 'word frequency' and other useful factors.
- Define multiple sorting targets for different collections or decks of cards.
- Customize the ranking factors for each target.
- Define a language for each field.
- Use multiple fields (such as 'front' *and* 'back') to influence the ranking.
- Multiple 'word frequency' lists can be used per language.

## Installation

1. Go to the Anki plugin folder, such as __C:\Users\%USERNAME%\AppData\Roaming\Anki2\addons21__
2. Create a new folder for the plugin, such as __addons21\FrequencyMan__
3. Clone the project in the new folder: `git clone https://github.com/Rct567/FrequencyMan.git`
4. Place your word frequency lists (*.txt files) in a subfolder, such as __\FrequencyMan\user_files\frequency_lists\en__
5. Start Anki.

## Basic usage

1. Open the "FrequencyMan" menu option in the __"Tools" menu__ of the main Anki window.
2. This will open the "FrequencyMan Main Window" where you can define your __sorting targets__.
3. Define your sorting targets using a JSON list of objects. Each object represents a target to sort (a target can be a deck or a defined collection of cards).
4. Click the __"Reorder Cards" button__ to apply the sorting.