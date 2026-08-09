// ArogyaX — Main JavaScript
// Mobile menu toggle is already handled inline in HTML

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

// Add scroll-based header shadow
window.addEventListener('scroll', () => {
    const header = document.querySelector('.header');
    if (header) {
        if (window.scrollY > 20) {
            header.style.boxShadow = '0 4px 24px rgba(0,0,0,0.4)';
        } else {
            header.style.boxShadow = 'none';
        }
    }
});

// Animate stats counter on homepage
function animateCounter(el, target) {
    let start = 0;
    const duration = 1500;
    const step = (timestamp) => {
        if (!start) start = timestamp;
        const progress = Math.min((timestamp - start) / duration, 1);
        const val = Math.floor(progress * target);
        el.textContent = val + '+';
        if (progress < 1) requestAnimationFrame(step);
        else el.textContent = target + '+';
    };
    requestAnimationFrame(step);
}

// Intersection observer for counter animation
const counters = document.querySelectorAll('.glass h3');
if (counters.length > 0) {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const rawText = entry.target.textContent.replace(/[^0-9]/g, '');
                const target = parseInt(rawText);
                if (!isNaN(target) && target > 0) {
                    animateCounter(entry.target, target);
                }
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });
    counters.forEach(c => observer.observe(c));
}

// File upload preview
document.querySelectorAll('input[type="file"]').forEach(input => {
    input.addEventListener('change', function() {
        const uploadBox = this.closest('.upload-box');
        if (uploadBox && this.files[0]) {
            const icon = uploadBox.querySelector('i');
            const texts = uploadBox.querySelectorAll('p');
            if (icon) icon.className = 'fas fa-check-circle';
            if (icon) icon.style.color = 'var(--success)';
            if (texts[0]) texts[0].textContent = 'File selected: ' + this.files[0].name;
            if (texts[1]) texts[1].textContent = 'Click Analyze to proceed';
        }
    });
});

// Flash message auto-dismiss
document.querySelectorAll('.flash-msg').forEach(msg => {
    setTimeout(() => {
        msg.style.opacity = '0';
        msg.style.transition = 'opacity 0.5s';
        setTimeout(() => msg.remove(), 500);
    }, 4000);
});