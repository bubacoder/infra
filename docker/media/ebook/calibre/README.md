Calibre is a powerful and easy to use e-book manager. Users say it's outstanding and a must-have.
It'll allow you to do nearly everything and it takes things a step beyond normal e-book software.
It's also completely free and open source and great for both casual users and computer experts.

Links:
- Home: https://calibre-ebook.com/
- Image: https://docs.linuxserver.io/images/docker-calibre/

Application setup:
- Create the library at `/books`
- For Readarr integration: Enable Content Server at Preferences -> Sharing over the net, enable "Require username and password to access the Content server"
- Optional: Install plugins at Preferences -> Get plugins

Book database (STORAGE_CALIBRE_LIBRARY) is not recommended to mounted via SMB due to locking issue ("DB appears locked").
A possible fix: https://www.mobileread.com/forums/showpost.php?s=2a2bb1273085bedaedd817ada675c7df&p=3460465&postcount=9
