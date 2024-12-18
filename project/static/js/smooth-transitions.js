// Smooth transitions for search and filter operations
class SmoothTransitions {
    constructor() {
        this.filterForm = document.getElementById('filterForm');
        this.productsContainer = document.getElementById('productsContainer');
        this.loadingOverlay = this.createLoadingOverlay();
        this.init();
    }

    init() {
        if (!this.filterForm || !this.productsContainer) return;

        // Add transition styles
        this.addTransitionStyles();

        // Handle form submission
        this.filterForm.addEventListener('submit', (e) => this.handleSubmit(e));

        // Handle price range inputs
        const minPrice = document.getElementById('minPrice');
        const maxPrice = document.getElementById('maxPrice');
        const minRange = document.getElementById('priceRangeMin');
        const maxRange = document.getElementById('priceRangeMax');

        if (minPrice && maxPrice && minRange && maxRange) {
            this.handlePriceRangeInputs(minPrice, maxPrice, minRange, maxRange);
        }

        // Handle sort options
        const sortInputs = document.querySelectorAll('input[name="sort"]');
        sortInputs.forEach(input => {
            input.addEventListener('change', () => {
                this.handleFilterChange();
            });
        });

        // Handle apply filters button
        const applyButton = document.getElementById('applyFilters');
        if (applyButton) {
            applyButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleFilterChange();
            });
        }

        // Handle pagination links
        document.querySelectorAll('.pagination .page-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const url = new URL(link.href);
                this.fetchProducts(url.search);
            });
        });
    }

    createLoadingOverlay() {
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="spinner-wrapper">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="mt-3 text-primary">Updating products...</div>
            </div>
        `;
        document.body.appendChild(overlay);
        return overlay;
    }

    addTransitionStyles() {
        const style = document.createElement('style');
        style.textContent = `
            #productsContainer {
                transition: all 0.3s ease;
            }
            .products-fade-out {
                opacity: 0;
                transform: translateY(10px);
            }
            .products-fade-in {
                opacity: 1;
                transform: translateY(0);
            }
            .loading-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(255, 255, 255, 0.8);
                backdrop-filter: blur(4px);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s ease;
            }
            .loading-overlay.active {
                opacity: 1;
                visibility: visible;
            }
            .spinner-wrapper {
                background: white;
                padding: 2rem;
                border-radius: 1rem;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                text-align: center;
            }
            .spinner-border {
                width: 3rem;
                height: 3rem;
            }
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            .product-card {
                animation: slideIn 0.3s ease forwards;
                animation-delay: calc(var(--product-index) * 0.05s);
                opacity: 0;
            }
        `;
        document.head.appendChild(style);
    }

    handlePriceRangeInputs(minPrice, maxPrice, minRange, maxRange) {
        // Update input when range changes
        minRange.addEventListener('input', () => {
            if (parseInt(minRange.value) > parseInt(maxRange.value)) {
                minRange.value = maxRange.value;
            }
            minPrice.value = minRange.value;
        });

        maxRange.addEventListener('input', () => {
            if (parseInt(maxRange.value) < parseInt(minRange.value)) {
                maxRange.value = minRange.value;
            }
            maxPrice.value = maxRange.value;
        });

        // Update range when input changes
        minPrice.addEventListener('input', () => {
            let value = parseInt(minPrice.value) || 0;
            if (value < 0) value = 0;
            if (value > parseInt(maxPrice.value || 10000)) {
                value = parseInt(maxPrice.value || 10000);
            }
            minPrice.value = value;
            minRange.value = value;
        });

        maxPrice.addEventListener('input', () => {
            let value = parseInt(maxPrice.value) || 10000;
            if (value < parseInt(minPrice.value || 0)) {
                value = parseInt(minPrice.value || 0);
            }
            maxPrice.value = value;
            maxRange.value = value;
        });
    }

    handleFilterChange() {
        const formData = new FormData(this.filterForm);
        const queryString = new URLSearchParams(formData).toString();
        this.fetchProducts('?' + queryString);
    }

    async handleSubmit(e) {
        e.preventDefault();
        this.handleFilterChange();
    }

    async fetchProducts(queryString) {
        // Start transition
        this.productsContainer.classList.add('products-fade-out');
        this.loadingOverlay.classList.add('active');

        try {
            // Update URL without reloading
            const newUrl = window.location.pathname + queryString;
            window.history.pushState({}, '', newUrl);

            // Fetch new content
            const response = await fetch(newUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) throw new Error('Network response was not ok');

            const html = await response.text();

            // Parse the HTML and get the products container content
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newProducts = doc.getElementById('productsContainer');

            // Wait for fade out animation
            await new Promise(resolve => setTimeout(resolve, 300));

            // Update content
            if (newProducts) {
                this.productsContainer.innerHTML = newProducts.innerHTML;
                
                // Reinitialize pagination links
                this.initPaginationLinks();
            }

            // Start fade in animation
            this.productsContainer.classList.remove('products-fade-out');
            this.productsContainer.classList.add('products-fade-in');

            // Add staggered animations to products
            this.addProductAnimations();

        } catch (error) {
            console.error('Error updating products:', error);
        } finally {
            // Hide loading overlay
            setTimeout(() => {
                this.loadingOverlay.classList.remove('active');
            }, 300);
        }
    }

    initPaginationLinks() {
        document.querySelectorAll('.pagination .page-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const url = new URL(link.href);
                this.fetchProducts(url.search);
            });
        });
    }

    addProductAnimations() {
        const products = document.querySelectorAll('.product-card');
        products.forEach((product, index) => {
            product.style.setProperty('--product-index', index);
        });
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const transitions = new SmoothTransitions();
    
    // Add animation to products after page load
    setTimeout(() => {
        transitions.addProductAnimations();
    }, 100);
}); 