// Подсветка выбранного плана из URL
const urlParams = new URLSearchParams(window.location.search);
const selectedPlan = urlParams.get('plan');

if (selectedPlan) {
    const planElement = document.getElementById(selectedPlan);
    if (planElement) {
        setTimeout(() => {
            planElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            planElement.style.boxShadow = '0 0 60px rgba(99, 102, 241, 0.3)';

            setTimeout(() => {
                planElement.style.boxShadow = '';
            }, 2000);
        }, 300);
    }
}