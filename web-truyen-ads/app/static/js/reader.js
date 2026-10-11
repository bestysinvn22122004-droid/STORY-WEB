// Reading Experience and Theme Controller for Web Truyen Ads
(function() {
    // 1. Reading Progress Bar
    const progressBar = document.getElementById('reading-progress');
    if (progressBar) {
        window.addEventListener('scroll', () => {
            const docElement = document.documentElement;
            const docBody = document.body;
            const scrollTop = docElement.scrollTop || docBody.scrollTop;
            const scrollHeight = (docElement.scrollHeight || docBody.scrollHeight) - docElement.clientHeight;
            const progress = (scrollTop / scrollHeight) * 100;
            progressBar.style.width = Math.min(100, Math.max(0, progress)) + '%';
        });
    }

    // 2. Reading Preferences (Font size, Theme, Font family)
    const storyContainer = document.getElementById('story-body');
    const rootElement = document.documentElement;

    // Load saved preferences
    const savedFontSize = localStorage.getItem('story_font_size') || 'text-lg';
    const savedTheme = localStorage.getItem('story_theme') || 'light';
    const savedFontFamily = localStorage.getItem('story_font_family') || 'font-serif';

    applyFontSize(savedFontSize);
    applyTheme(savedTheme);
    applyFontFamily(savedFontFamily);

    window.setFontSize = function(sizeClass) {
        applyFontSize(sizeClass);
        localStorage.setItem('story_font_size', sizeClass);
    };

    window.setStoryTheme = function(themeName) {
        applyTheme(themeName);
        localStorage.setItem('story_theme', themeName);
    };

    window.setStoryFontFamily = function(familyClass) {
        applyFontFamily(familyClass);
        localStorage.setItem('story_font_family', familyClass);
    };

    function applyFontSize(sizeClass) {
        if (!storyContainer) return;
        storyContainer.classList.remove('text-base', 'text-lg', 'text-xl', 'text-2xl');
        storyContainer.classList.add(sizeClass);

        // Highlight active font button
        document.querySelectorAll('.font-size-btn').forEach(btn => {
            if (btn.dataset.size === sizeClass) {
                btn.classList.add('bg-amber-100', 'text-amber-900', 'border-amber-400', 'dark:bg-amber-900/40', 'dark:text-amber-200');
            } else {
                btn.classList.remove('bg-amber-100', 'text-amber-900', 'border-amber-400', 'dark:bg-amber-900/40', 'dark:text-amber-200');
            }
        });
    }

    function applyTheme(themeName) {
        rootElement.classList.remove('dark', 'sepia-mode');
        document.body.classList.remove('bg-amber-50/50', 'bg-gray-900', 'text-gray-100', 'text-gray-900');

        if (themeName === 'dark') {
            rootElement.classList.add('dark');
            document.body.classList.add('bg-gray-950', 'text-gray-100');
        } else if (themeName === 'sepia') {
            rootElement.classList.add('sepia-mode');
            document.body.classList.add('bg-[#fbf0d9]', 'text-[#433422]');
        } else {
            document.body.classList.add('bg-stone-50', 'text-gray-900');
        }

        // Highlight active theme button
        document.querySelectorAll('.theme-btn').forEach(btn => {
            if (btn.dataset.theme === themeName) {
                btn.classList.add('ring-2', 'ring-amber-500');
            } else {
                btn.classList.remove('ring-2', 'ring-amber-500');
            }
        });
    }

    function applyFontFamily(familyClass) {
        if (!storyContainer) return;
        storyContainer.classList.remove('font-serif', 'font-sans');
        storyContainer.classList.add(familyClass);
    }

    // 3. Sticky Bottom Ad Close Functionality
    window.closeStickyAd = function() {
        const stickyAd = document.getElementById('sticky-bottom-ad');
        if (stickyAd) {
            stickyAd.style.display = 'none';
        }
    };

    // 4. Social Sharing Helpers
    window.shareFacebook = function(url) {
        const shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url || window.location.href)}`;
        window.open(shareUrl, '_blank', 'width=600,height=500');
    };

    window.copyStoryLink = function() {
        navigator.clipboard.writeText(window.location.href).then(() => {
            const toast = document.getElementById('copy-toast');
            if (toast) {
                toast.classList.remove('hidden');
                setTimeout(() => toast.classList.add('hidden'), 3000);
            } else {
                alert('Đã sao chép liên kết truyện vào bộ nhớ tạm!');
            }
        });
    };
})();
