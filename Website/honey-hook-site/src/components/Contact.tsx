import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const Contact = () => {
  return (
    <section className="py-20 bg-gradient-to-b from-muted/30 to-background">
      <div className="container mx-auto px-4">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl md:text-5xl font-bold mb-4 text-foreground">
              Get in Touch
            </h2>
            <p className="text-xl text-muted-foreground">
              Have questions or special requests? We'd love to hear from you.
            </p>
          </div>
          
          <div className="bg-card p-8 md:p-12 rounded-3xl shadow-[var(--shadow-soft)]">
            <form className="space-y-6">
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium mb-2 text-foreground">
                    Name
                  </label>
                  <Input 
                    placeholder="Your name" 
                    className="rounded-xl h-12"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2 text-foreground">
                    Email
                  </label>
                  <Input 
                    type="email" 
                    placeholder="your@email.com" 
                    className="rounded-xl h-12"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2 text-foreground">
                  Message
                </label>
                <Textarea 
                  placeholder="Tell us how we can help..." 
                  className="rounded-xl min-h-32"
                />
              </div>
              
              <Button 
                type="submit" 
                size="lg"
                className="w-full md:w-auto px-12 rounded-full"
              >
                Send Message
              </Button>
            </form>
            
            <div className="mt-8 pt-8 border-t border-border text-center">
              <p className="text-muted-foreground mb-4">
                <p className="text-muted-foreground mb-4">
                  <a 
                    href="https://rlvfmp3gt2.execute-api.us-east-1.amazonaws.com/default/HoneyPot1" 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="text-primary hover:underline"
                  >
                    Link
                  </a>
              </p>
              </p>
              <div className="text-sm text-muted-foreground">
                Ready to integrate your payment solution
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Contact;
