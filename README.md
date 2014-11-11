### homestuck_update_bot ###

This is an MSPA-specific update bot that post updates it finds to Reddit.

Rather than using the RSS feed to detect updates, it uses the txt files (e.g. http://www.mspaintadventures.com/6/001901.txt). This is not only a lot simpler to code (MSPA's RSS is a mess), but also it minimizes bandwidth usage: only about 305 bytes are transferred in a HEAD request/response.