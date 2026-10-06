	var button_up = keyboard_check(up)
	var button_down = keyboard_check(down)
	move = button_up - button_down
	
	var _target_spd = move * spd
	
	fluid_movement = lerp(fluid_movement, _target_spd, 0.4)

	y += fluid_movement

if (y>=SCREEN_HEIGHT){
	
	instance_destroy()

}