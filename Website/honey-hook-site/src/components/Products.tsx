import { Button } from "@/components/ui/button";

const products = [
  {
    name: "Wildflower Honey",
    size: "500g",
    description: "A delicate blend from diverse wildflowers",
    price: "$18",
  },
  {
    name: "Clover Honey",
    size: "500g",
    description: "Light and sweet with a smooth finish",
    price: "$16",
  },
  {
    name: "Raw Honeycomb",
    size: "300g",
    description: "Pure honey in its natural form",
    price: "$22",
  },
];

const Products = () => {
  return (
    <section className="py-20 bg-background">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4 text-foreground">
            Our Collection
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Each variety offers a unique flavor profile and natural goodness.
          </p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {products.map((product, index) => (
            <div
              key={index}
              className="bg-card rounded-3xl overflow-hidden shadow-[var(--shadow-soft)] hover:shadow-xl transition-shadow duration-300"
            >
              <div className="h-64 bg-gradient-to-br from-secondary/20 to-primary/20 flex items-center justify-center">
                <div className="text-8xl">🍯</div>
              </div>
              <div className="p-6">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-2xl font-bold text-foreground">
                    {product.name}
                  </h3>
                  <span className="text-2xl font-bold text-primary">
                    {product.price}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground mb-2">{product.size}</p>
                <p className="text-muted-foreground mb-6">{product.description}</p>
                <Button 
                  className="w-full rounded-full"
                  size="lg"
                >
                  Add to Cart
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Products;
