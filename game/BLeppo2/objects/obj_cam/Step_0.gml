x = cam_x
y = cam_y

shake_time --
shake_time_strong --
if(shake_time > 0) {
	x += random_range(-1,1)
	y += random_range(-1,1)
}
if(shake_time_strong > 0) {
	x += random_range(-4,4)
	y += random_range(-4,4)
}
camera_set_view_pos(view_camera[0], x - SCREEN_WIDTH/2 + 16, y - SCREEN_HEIGHT/2 + 16)