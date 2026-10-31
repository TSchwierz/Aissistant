---
description: This file details the features that the finished project should have. It is non-exhausting and omits technical details, but shows a n overview of the core concepts that should be fulfilled.
---

# Server
- always active 
- regularly reads temperature and humidity from sensor
- scans for bluetooth transmittion from weight scale via either: manual I/O, or a daily scheduled "on" periode between 8 and 10 AM. 
- A buzzer element is used by the server=pi to make a short sound to acknowledge that data from the scale has been read
- Pre-Generates morning briefs during the night
- endpoints are protected via api key authorisation
- A stopped climate sampler, scale scanner, or news job is restarted on its own, without taking the API down
- Keeps AI API keys on the Pi and uses them to summarize news and to turn a meal description or photo into calories
- Collects scheduled news digests from RSS and Atom feeds
- Composes a morning brief from the day's weather, calendar, and news
- Records an indoor incident when temperature or humidity stays outside the set bands, and can push a phone notification for it
- Exports a backup of its databases

# Web

## Weather
- Shows detailed hourly outside weather forecast for the next 24h
- Has charts and plots of the indoor measurements from the server
- Shows the current indoor temperature and humidity, and whether airing out would help
- Plots indoor history over 12 hours, 24 hours, 7 days, or 30 days
- Shows the current outside reading from Open-Meteo, Bright Sky, and OpenWeatherMap
- Lets the comfort bands and the indoor sample interval be edited

## Calendar
- syncs automatically with the server (source of truth)
- Import from file
- Tags 
- Reminders
- Creating/editing events can be done in a tempo painting style over the week views
- Week, two-week, month, and list views
- Events can repeat every week, every two weeks, or monthly, with an optional end date
- Tag colours

## Health
- Detailed reports and charts
- I/O weight scale signal scanning + set automatic schedule
- Latest weight and body composition, plus charts over 30 days, 90 days, a year, or all history
- A measurement list, including readings entered by hand
- Body profile and nutrition targets
- A meal log with food search, barcode lookup, and calories parsed from text or a photo

## News
- Topics, each with a goal, feeds, and a schedule
- The latest digest for each topic

## Morning brief
- Shows today's script and its sections

## Settings
- Pi address, a connection test, backup download, and theme (system, dark, or light, with an accent colour)

# Mobile
- Connect from anywhere -> server access with api key
- Climate, health, news, and settings follow the same sections as the web UI
- Start, stop, or return the scale listener to its schedule
- Log a meal from a barcode or a photo

## Morning brief
- receives a morning brief in text form from the server
- Has a TTS voice the brief out loud
- Exposes an app action to be used in android routines
- Shows the brief sections on screen, and can be opened from inside the app

## Calendar
- syncs automatically with server
- keeps local data for the upcoming 7 days
- sends notifications for event reminders
- Month and two-week views, with tags and create, edit, and delete
