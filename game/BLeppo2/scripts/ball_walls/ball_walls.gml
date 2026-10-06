function ball_walls(){
	// Effetto Pac-Man sui bordi orizzontali
    if (x > room_width)  { x = 0; }
    if (x < 0)           { x = room_width; }
    
    // Effetto Pac-Man sui bordi verticali
    if (y > room_height) { y = 0; }
    if (y < 0)           { y = room_height; }
	
}