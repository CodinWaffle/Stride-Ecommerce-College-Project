document.addEventListener('DOMContentLoaded', function() {
    const minPriceInput = document.getElementById('minPrice');
    const maxPriceInput = document.getElementById('maxPrice');
    const minRange = document.getElementById('priceRangeMin');
    const maxRange = document.getElementById('priceRangeMax');
    const sortSelect = document.getElementById('sortSelect');
    const applyFilters = document.getElementById('applyFilters');

    // Initialize ranges
    minRange.value = minPriceInput.value;
    maxRange.value = maxPriceInput.value;

    // Update input when range changes
    minRange.addEventListener('input', function() {
        if (parseInt(minRange.value) > parseInt(maxRange.value)) {
            minRange.value = maxRange.value;
        }
        minPriceInput.value = minRange.value;
    });

    maxRange.addEventListener('input', function() {
        if (parseInt(maxRange.value) < parseInt(minRange.value)) {
            maxRange.value = minRange.value;
        }
        maxPriceInput.value = maxRange.value;
    });

    // Update range when input changes
    minPriceInput.addEventListener('input', function() {
        let value = parseInt(this.value);
        if (value < 0) value = 0;
        if (value > parseInt(maxPriceInput.value)) {
            value = parseInt(maxPriceInput.value);
        }
        this.value = value;
        minRange.value = value;
    });

    maxPriceInput.addEventListener('input', function() {
        let value = parseInt(this.value);
        if (value < parseInt(minPriceInput.value)) {
            value = parseInt(minPriceInput.value);
        }
        if (value > 1000) value = 1000;
        this.value = value;
        maxRange.value = value;
    });

    // Apply filters
    applyFilters.addEventListener('click', function() {
        const currentUrl = new URL(window.location.href);
        const params = currentUrl.searchParams;

        // Update or add price parameters
        params.set('min_price', minPriceInput.value);
        params.set('max_price', maxPriceInput.value);

        // Keep existing category if present
        const category = params.get('category');
        if (category) {
            params.set('category', category);
        }

        // Keep existing sort if present
        const sort = params.get('sort');
        if (sort) {
            params.set('sort', sort);
        }

        window.location.href = currentUrl.toString();
    });

    // Initialize values from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('min_price')) {
        const minPrice = urlParams.get('min_price');
        minPriceInput.value = minPrice;
        minRange.value = minPrice;
    }
    if (urlParams.has('max_price')) {
        const maxPrice = urlParams.get('max_price');
        maxPriceInput.value = maxPrice;
        maxRange.value = maxPrice;
    }

    // Sort select handler
    sortSelect.addEventListener('change', function() {
        window.location.href = this.value;
    });

    // Update the pagination links to include price range
    document.querySelectorAll('.pagination .page-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const url = new URL(this.href);
            const currentUrl = new URL(window.location.href);
            
            // Add price range to pagination URL if exists
            if (currentUrl.searchParams.has('min_price')) {
                url.searchParams.set('min_price', currentUrl.searchParams.get('min_price'));
            }
            if (currentUrl.searchParams.has('max_price')) {
                url.searchParams.set('max_price', currentUrl.searchParams.get('max_price'));
            }
            
            window.location.href = url.toString();
        });
    });
}); 