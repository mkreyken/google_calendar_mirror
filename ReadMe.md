# Overview
* Sync several Venue (secondary) Calendars into a single shared mirror calendar
* Ensure sharing is not enabled on the venue calendars
* Run in the tray so it can be disabled, and can run reports

# Timezonss:
* Recurring events shift with the timezone as it moves along, so using single_events, and including timezone in the computation,
* ensures no issues

# Operation
* The Policies of the Organization in Google, is not to allow users to publish primary calendars Visibly externally, but secondaries can be shared externally.
* This will hide data from the venue calendars to the shared mirror, it will also ensure that the venues aer not shared.
* 
* It Combines 3 basic operation : 
* - Windowed sync - THe mirror is kept locally and "windowed" across that desired months
* - Windowed - THe calendars can be window resynced, to ensure they are accurate across the window
* - Full - all calendars are rebuilt
* - Incremental, from the next Full sync, use the token, and the window sync does not impact this
* (Google filtered and syncs do not interact)
* It uses a single_event calendar moving 18 months into the future and
* does full syncs at intervals to ensure that the mirror is reasonable accurate
* 
# How Google Calendar Setup:
* Google uses a unique id for each entry, this means that the entries in one calendar are not the same id as entries in another calendar
* To match these, then we need to identify which entries in the mirror match the entries in the main calendar,
* AND we need to have both id's (original and mirror) so we Update or Create.
* rather than scrub and then add all
* 
* We don't use the uCalid in the mirror to auto delete and recreate the events, but keep
* a local cross-reference to allow for updates. This keeps the downstream consumers from seeing deletes and adds
* and makes reoccurrence modeling possible if we change from single_event handling

# Reoccurring events and orderby/singleEvent/syncToken
* Inorder to appropriately match reoccurring events between the receiving event and the mirror calendar
* We need to have singleEvent = false, this eliminates orderby=startTime
* Using syncToken also eliminates orderby=startTime
* So we need to decide what the mirror calendar will look like - single events or reoccurring events

* Single events =true eliminate the issue of looking into the far past to see reoccurring events in the far future,
* If we use single Events, we can mirror the calendar in the appropriate window of time, as we are mirroring the 
* Single events with the last data.

# Push versus Poll
* Push is always considered unreliable, but is used for immediate distribution, however, we don't need immediate mirroring, we need least complex and accurate
* Pull using a sync id always provides for a complete data set, especially if you don't write the update id until AFTER the sync is completed.
* 
# Data on Disk
* Simple - one JSON file per calendar_id (event though they all come from the mirror)
* ON full sync, 
*    delete anything that comes in from an invalid calendar id
*    delete anything tht has a duplicate sync id
*    write to disk
*  Then per calendar_id, do a merge from original
*    Since it is ordered - 
*       Delete, add or update in the mirror
*    write to disk,
*    write sync data to disk
* ON Partial sync
*   Read the table 
*   update
*   write to table
*   write sync id to table
* since partial work is not important to save, we don't need to save in process

* Calendar_ids, are not persisted, they are loaded on
* start to ensure things have not changed

* To start as Python
* cd to src directory and  python -m src.services.launcher