# KaviBOT connections - Seth's 5 steps

The code is built and tested (57/57). Nothing is installed on your PC yet
and KaviBOT can't use any of it until you do these steps. Nothing here
costs money.

## Step 1 - Google Cloud project (free, ~10 min, one time)

This lets KaviBOT read your Google Calendar ("plan my day").

1. Go to console.cloud.google.com, sign in, create a project (any name, e.g. `KaviBOT`).
2. **APIs & Services -> Library** -> search **Google Calendar API** -> Enable.
3. **APIs & Services -> OAuth consent screen** -> User type **External** -> fill
   app name + your email -> add scope
   `https://www.googleapis.com/auth/calendar.readonly` -> Save.
4. **APIs & Services -> Credentials -> Create credentials -> OAuth client ID** ->
   Application type **Desktop app** -> Create. Copy the **Client ID** (and the
   client secret - you'll paste both once, then they're locked in KaviBOT's
   vault and never shown again).
5. **Important, don't skip:** **APIs & Services -> Audience -> Publish app**.
   Google kills refresh tokens after 7 days for apps left in "Testing" mode;
   publishing is free, instant, and needs no review. (Publishing asks for a
   homepage + privacy-policy link - a bare-bones GitHub Pages page works.)
6. When you connect in Step 4, Google shows "Google hasn't verified this
   app" - click **Advanced -> Go to KaviBOT (unsafe)**. That's expected for a
   personal app; it just means Google didn't review it.

## Step 2 - Amazon developer console (2 min, conditional)

You said you're an Amazon developer - the Amazon Music API is closed beta,
but they may enable it on your security profile:

1. Open your Amazon developer console -> check whether **Amazon Music API**
   access is available/enabled on your security profile.
2. If yes (or you can request it): tell me and I'll build the Amazon Music
   adapter - the framework already speaks its login style, it's a small
   add-on. If no: nothing lost, the Apple Music import in Step 3 covers your
   music tastes.

## Step 3 - Export your Apple Music library (3 clicks, free)

This is how KaviBOT learns your music tastes - no subscription API needed.

- **Mac:** open the Music app -> **File -> Library -> Export Library** -> save `Library.xml`.
- **Windows:** open **iTunes** (free download if you don't have it - the newer
  Apple Music app for Windows doesn't offer a full-library export) ->
  **File -> Library -> Export Library** -> save `Library.xml`.

The file stays on your PC. KaviBOT only keeps the derived taste profile
(top artists, genres, loved tracks) - never uploads your library anywhere.

## Step 4 - Install + connect (on your PC)

I'll paste you a one-line installer when the code is mirrored (it downloads
everything fresh - you don't carry any files). Then:

```
python C:\AI\connections\kavibot-connect.py connect gcal
```
A browser window opens -> sign in -> approve. Paste the Client ID/secret from
Step 1 when asked (once).

```
python C:\AI\connections\kavibot-connect.py import apple_music "C:\path\to\Library.xml"
```

## Step 4b - iCloud (2 min, free, optional)

KaviBOT can also read your iCloud Mail, Calendar, and Contacts - no Apple
developer fee, just an app-specific password:

1. Go to **appleid.apple.com** -> sign in -> **Sign-In and Security** ->
   **App-Specific Passwords** -> generate one (name it `KaviBOT`).
2. On your PC:
```
python C:\AI\connections\kavibot-connect.py connect icloud
```
Paste your Apple ID email, then the app-specific password, when asked.
The password goes straight into the PC vault - it's never shown again.
Revoke it anytime at appleid.apple.com.

## Step 5 - Verify it worked

```
python C:\AI\connections\kavibot-connect.py call gcal list_events
```
You should see your upcoming events. Then ask KaviBOT in Open WebUI:
"what's on my calendar tomorrow" - and "what do you know about my music
taste". If either answer is wrong or empty, tell me exactly what it said.

---

**What you never have to do:** no Premium, no paid Apple/Amazon developer
fees, no passwords in chat. Secrets go through the on-screen prompts
straight into the PC vault.

**What's still parked:** Spotify (needs Premium - your call if that ever
changes), live Apple Music API ($99/yr Apple fee - no).
