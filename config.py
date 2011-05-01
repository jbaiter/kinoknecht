# Database setup
db_file = ":memory:"
log_file = "debug.log"
log_level = "debug"
video_dirs = ["tests/testdir"]

# Server setup
address = 'localhost'
port = 6600

# Player setup
extra_args = "-vo fbdev2 -xy 800 -zoom -fs -softvol"
framebuffer_out = True
