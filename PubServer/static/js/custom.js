$(function(){
	'use-strict';

	// sidenav control right
	$(".sidenav-control-right").sideNav({
		
		edge: 'right',
		closeOnClick: false

	});

	// panel collapse icon
	$(document).on("click",".collapsible-header",function(){
	    $(this).find('span i').toggleClass('fa-chevron-down')
	});

	// slick slider
	$('.slider-slick').slick({
		
		dots: true,
		infinite: true,
		speed: 300,
		slidesToShow: 1,
		autoplay: true

	});
	
	// faq collapse icon
	$(document).on("click",".faq-collapsible",function(){
	    $(this).find('i').toggleClass('fa-minus')
	});

	// splash
	$("#splash").owlCarousel({
 
      	slideSpeed : 300,
      	paginationSpeed : 400,
      	singleItem: true,

  	});

	// testimonial
	$("#testimonial").owlCarousel({
 
      	slideSpeed : 300,
      	paginationSpeed : 400,
      	singleItem: true,

  	});


	// tabs
	$('ul.tabs').tabs(); 
        

});