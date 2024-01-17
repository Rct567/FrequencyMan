# FrequencyMan (Anki Plugin)

## Overview

As an Anki plugin, __FrequencyMan__ goal is to optimize your Anki learning journey by allowing you to intelligently __sort your new cards__ in a personalized way.

Please note: this plugin is a __WORK IN PROGRESS__. Don't use it on your main profile!

## Features
- Sort cards based on 'word frequency' and other useful factors.
- Define multiple sorting targets for different decks or selection of cards.
- Customize the ranking factors for each target.
- Define a language for each field.
- Use multiple fields (such as 'front' *and* 'back') to influence the ranking.
- Multiple 'word frequency' lists can be used per language.

## Installation

1. Go to the Anki plugin folder, such as __C:\Users\%USERNAME%\AppData\Roaming\Anki2\addons21__
2. Create a new folder for the plugin, such as __addons21\FrequencyMan__
3. Clone the project in the new folder: `git clone https://github.com/Rct567/FrequencyMan.git`
4. Place your word frequency lists (*.txt files) in a subfolder in FrequencyMan/user_files/, such as __\FrequencyMan\user_files\lang_data\en__. If multiple lists exists for a language, they will be combined (based on highest score/position).
5. Start Anki.

## Download word frequency lists

- Based on Open Subtitles: https://github.com/hermitdave/FrequencyWords/tree/master
- Based on Wikipedia: https://github.com/IlyaSemenov/wikipedia-word-frequency

## Basic usage

1. Open the "FrequencyMan" menu option in the __"Tools" menu__ of the main Anki window.
2. This will open the "FrequencyMan Main Window" where you can define your __sorting targets__.
3. Define the targets using a JSON list of objects. Each object represents a target to sort (a target can be a deck or a defined selection of cards).
4. Click the __"Reorder Cards" button__ to apply the sorting.

## Configuration examples

### Example 1
Reorders a single deck. This will only match cards with note type `-- My spanish --` located in deck `Spanish`. It will also use the default ranking factors.

The content of your cards and all the ranking metrics will be analyzed per field. The result of this will be combined to determine the final ranking of all new cards. Each field is effectively its own little "universe".

Note: For both languages, a word frequency list file should exist (although it could be empty).

```json
[
    {
        "deck": "Spanish",
        "notes": [
            {
                "fields": {
                    "Meaning": "EN",
                    "Sentence": "ES"
                },
                "name": "-- My spanish --"
            }
        ]
    }
]
```


### Example 2
Reorder the same deck twice, but the first target excludes the sorting of cards whose name matches "Speaking", while the second target only sorts those excluded cards.

The first target only modifies a single ranking factor (giving familiar cards a boost), while the second target reduces the ranking factors used to only 2 factors (with the aim to order by 'as easy as possible').

Note: Both targets use the same 'main scope', which is the selection of cards used to create the data to calculate the ranking. This scope is reduced for each target by `reorder_scope_query` to limit which cards get repositioned.

```json
[
    {
        "deck": "Spanish",
        "notes": [
            {
                "fields": {
                    "Meaning": "EN",
                    "Sentence": "ES"
                },
                "name": "-- My spanish --"
            }
        ],
        "reorder_scope_query": "-card:*Speaking*",
        "ranking_familiarity_scores": 2
    },
    {
        "deck": "Spanish",
        "notes": [
            {
                "fields": {
                    "Meaning": "EN",
                    "Sentence": "ES"
                },
                "name": "-- My spanish --"
            }
        ],
        "reorder_scope_query": "card:*Speaking*",
        "ranking_factors": {
            "familiarity_scores": 1,
            "lowest_fr_word_score": 1
        }
    }
]
```

### Example #3
Reorder only based on word frequency (using word frequency from both front and back):

```json
[
    {
        "deck": "Spanish::Essential Spanish Vocabulary Top 5000",
        "notes": [
            {
                "name": "Basic-f4e28",
                "fields": {
                    "Spanish": "ES",
                    "English": "EN"
                }
            }
        ],
        "ranking_factors": {
            "words_fr_score": 1
        }
    }
]
```

## Tokenizers

Custom tokenizers can be defined in `user_files\tokenizers`.

To use, or to see how a custom tokenizer is defined, you can download [here](https://github.com/Rct567/FrequencyMan_tokenizer_jieba) a working copy of Jieba (ZH), and [here](https://github.com/Rct567/FrequencyMan_tokenizer_janome) a version of Janome (JA).

### Automatic support

FrequencyMan will use tokenizers from other plugins, if there is no custom tokenizer for a given language:

- If [AJT Japanese](https://ankiweb.net/shared/info/1344485230) is installed, Mecab can be used.
- If [Morphman](https://ankiweb.net/shared/info/900801631) is installed, Mecab and Jieba can be used (assuming those also work in Morphman itself).