var type = async_load[? "type"];
if (type == network_type_data) {
    var buff = async_load[? "buffer"];
    
    if (buffer_exists(buff) && buffer_get_size(buff) > 0) {
        var data = buffer_read(buff, buffer_string);
        show_debug_message("Onda: " + string(data));
        
        var newx = x;
        var newy = y;
        
        if (data == "g") { newy -= spd; }
        if (data == "b") { newx += spd; }
        if (data == "a") { newx -= spd; }
        
        if (!place_meeting(newx, newy, obj_muro)) {
            x = newx;
            y = newy;
        }
        
        if (x > room_width)  { x = 0; }
        if (x < 0)           { x = room_width; }
        if (y > room_height) { y = 0; }
        if (y < 0)           { y = room_height; }
    }
}