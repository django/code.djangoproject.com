jQuery(document).ready(function($) {
	var menu = $('[role="banner"] [role="navigation"]');
	var button = $('<div class="menu-button"><i class="icon icon-reorder"></i><span>Menu</span></div>');

	menu.addClass('nav-menu-on');
	button.insertBefore(menu);
	button.on('click', function(){
		menu.toggleClass('active');
		button.toggleClass('active')
	});
})
