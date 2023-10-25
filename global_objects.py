import pynvim

nvim = pynvim.attach("child", argv=["/usr/bin/env", "nvim", "--embed", "--headless"])