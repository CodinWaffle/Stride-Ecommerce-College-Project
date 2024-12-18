let menuIcon = document.querySelector('#menu-icon');
let navbar = document.querySelector('.navbar');

if (menuIcon && navbar) {
    menuIcon.onclick = () => {
        navbar.classList.toggle('active');
    };

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!menuIcon.contains(e.target) && !navbar.contains(e.target)) {
            navbar.classList.remove('active');
        }
    });

    // Close menu when scrolling
    window.onscroll = () => {
        navbar.classList.remove('active');
    }; 
} 