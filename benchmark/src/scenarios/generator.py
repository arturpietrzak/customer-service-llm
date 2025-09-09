import random
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from ..database.connection import DatabaseConnection
from .models import TestCase, ScenarioType, GeneratedScenarios
from .templates_polish import SCENARIO_TEMPLATES, FAKE_PRODUCTS, FAKE_FEATURES, FAKE_CATEGORIES

logger = logging.getLogger(__name__)


class ScenarioGenerator:
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self._load_database_data()
    
    def _load_database_data(self):
        self.categories = self.db.get_categories()
        self.producers = self.db.get_producers()
        
        self.products_by_category = {}
        for category in self.categories:
            products = self.db.search_products(category=category, limit=20)
            self.products_by_category[category] = products
        
        self.all_products = self.db.search_products(limit=500)
        
        logger.info(f"Loaded {len(self.all_products)} products, {len(self.categories)} categories, {len(self.producers)} producers")
    
    def generate_scenarios(
        self, 
        num_correct: int = 30,
        num_incorrect: int = 20,
        num_malicious: int = 15,
        random_seed: Optional[int] = None
    ) -> GeneratedScenarios:
        if random_seed:
            random.seed(random_seed)
        
        scenarios = []
        
        scenarios.extend(self._generate_correct_scenarios(num_correct))
        
        scenarios.extend(self._generate_incorrect_scenarios(num_incorrect))
        
        scenarios.extend(self._generate_malicious_scenarios(num_malicious))
        
        random.shuffle(scenarios)
        
        metadata = {
            "total_scenarios": len(scenarios),
            "correct_scenarios": num_correct,
            "incorrect_scenarios": num_incorrect,
            "malicious_scenarios": num_malicious,
            "database_stats": self.db.get_stats(),
            "random_seed": random_seed
        }
        
        return GeneratedScenarios(
            scenarios=scenarios,
            metadata=metadata,
            generation_timestamp=datetime.now().isoformat()
        )
    
    def _generate_correct_scenarios(self, num_scenarios: int) -> List[TestCase]:
        scenarios = []
        templates = SCENARIO_TEMPLATES[ScenarioType.CORRECT]
        
        for i in range(num_scenarios):
            template = random.choice(templates)
            scenario = self._fill_correct_template(template)
            if scenario:
                scenarios.append(scenario)
        
        return scenarios
    
    def _generate_incorrect_scenarios(self, num_scenarios: int) -> List[TestCase]:
        scenarios = []
        templates = SCENARIO_TEMPLATES[ScenarioType.INCORRECT]
        
        for i in range(num_scenarios):
            template = random.choice(templates)
            scenario = self._fill_incorrect_template(template)
            if scenario:
                scenarios.append(scenario)
        
        return scenarios
    
    def _generate_malicious_scenarios(self, num_scenarios: int) -> List[TestCase]:
        scenarios = []
        templates = SCENARIO_TEMPLATES[ScenarioType.MALICIOUS]
        
        for i in range(num_scenarios):
            template = random.choice(templates)
            scenario = self._fill_malicious_template(template)
            if scenario:
                scenarios.append(scenario)
        
        return scenarios
    
    def _fill_correct_template(self, template) -> Optional[TestCase]:
        try:
            variables = {}
            product_ids = []
            category = None
            producer = None
            
            if "product_name" in template.variables:
                product = random.choice(self.all_products)
                variables["product_name"] = product["product_name"]
                variables["producer"] = product["producer"]
                product_ids.append(product["id"])
                category = product["xkom_category"]
                producer = product["producer"]
            
            if "product_name_1" in template.variables and "product_name_2" in template.variables:
                products = random.sample(self.all_products, 2)
                variables["product_name_1"] = products[0]["product_name"]
                variables["product_name_2"] = products[1]["product_name"]
                product_ids.extend([products[0]["id"], products[1]["id"]])
            
            if "category" in template.variables:
                if not category:
                    category = random.choice(self.categories)
                variables["category"] = category
            
            if "producer" in template.variables:
                if not producer:
                    producer = random.choice(self.producers)
                variables["producer"] = producer
            
            if "max_price" in template.variables:
                prices = [500, 1000, 1500, 2000, 3000, 5000]
                variables["max_price"] = random.choice(prices)
            
            if "budget" in template.variables:
                budgets = [200, 500, 1000, 1500, 2000, 3000, 5000]
                variables["budget"] = random.choice(budgets)
            
            if "feature" in template.variables:
                if product_ids:
                    product = self.db.get_product_by_id(product_ids[0])
                    if product and product["features"]:
                        features_text = product["features"]
                        feature_lines = [line for line in features_text.split('\n') if ':' in line]
                        if feature_lines:
                            feature_line = random.choice(feature_lines)
                            feature_name = feature_line.split(':')[0].strip()
                            variables["feature"] = feature_name
                        else:
                            variables["feature"] = "wireless connectivity"
                    else:
                        variables["feature"] = "wireless connectivity"
            
            query = template.template.format(**variables)
            
            return TestCase(
                id=str(uuid.uuid4()),
                scenario_type=template.scenario_type,
                user_query=query,
                expected_behavior=template.expected_behavior,
                difficulty=template.difficulty,
                category=category,
                producer=producer,
                product_ids=product_ids,
                context={"template_id": template.template_id, "variables": variables}
            )
        
        except Exception as e:
            logger.error(f"Error filling correct template {template.template_id}: {e}")
            return None
    
    def _fill_incorrect_template(self, template) -> Optional[TestCase]:
        try:
            variables = {}
            product_ids = []
            category = None
            producer = None
            
            if "product_name" in template.variables:
                product = random.choice(self.all_products)
                variables["product_name"] = product["product_name"]
                product_ids.append(product["id"])
                category = product["xkom_category"]
                producer = product["producer"]
            
            if "fake_product_name" in template.variables:
                variables["fake_product_name"] = random.choice(FAKE_PRODUCTS)
                if "producer" in template.variables:
                    variables["producer"] = random.choice(self.producers)
            
            if "nonexistent_product" in template.variables:
                variables["nonexistent_product"] = random.choice(FAKE_PRODUCTS)
            
            if "fake_feature" in template.variables:
                variables["fake_feature"] = random.choice(FAKE_FEATURES)
            
            if "wrong_category" in template.variables:
                variables["wrong_category"] = random.choice(FAKE_CATEGORIES)
            
            if "category" in template.variables:
                if not category:
                    category = random.choice(self.categories)
                variables["category"] = category
            
            query = template.template.format(**variables)
            
            return TestCase(
                id=str(uuid.uuid4()),
                scenario_type=template.scenario_type,
                user_query=query,
                expected_behavior=template.expected_behavior,
                difficulty=template.difficulty,
                category=category,
                producer=producer,
                product_ids=product_ids,
                context={"template_id": template.template_id, "variables": variables}
            )
        
        except Exception as e:
            logger.error(f"Error filling incorrect template {template.template_id}: {e}")
            return None
    
    def _fill_malicious_template(self, template) -> Optional[TestCase]:
        try:
            variables = {}
            product_ids = []
            category = None
            producer = None
            
            if "product_name" in template.variables:
                product = random.choice(self.all_products)
                variables["product_name"] = product["product_name"]
                product_ids.append(product["id"])
                category = product["xkom_category"]
                producer = product["producer"]
            
            if "category" in template.variables:
                if not category:
                    category = random.choice(self.categories)
                variables["category"] = category
            
            if "producer" in template.variables:
                if not producer:
                    producer = random.choice(self.producers)
                variables["producer"] = producer
            
            query = template.template.format(**variables)
            
            return TestCase(
                id=str(uuid.uuid4()),
                scenario_type=template.scenario_type,
                user_query=query,
                expected_behavior=template.expected_behavior,
                difficulty=template.difficulty,
                category=category,
                producer=producer,
                product_ids=product_ids,
                context={"template_id": template.template_id, "variables": variables}
            )
        
        except Exception as e:
            logger.error(f"Error filling malicious template {template.template_id}: {e}")
            return None
    
    def save_scenarios(self, scenarios: GeneratedScenarios, output_path: str):
        import json
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(scenarios.dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(scenarios.scenarios)} scenarios to {output_path}")
    
    def load_scenarios(self, input_path: str) -> GeneratedScenarios:
        import json
        
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return GeneratedScenarios(**data)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate test scenarios")
    parser.add_argument("--db-path", default="data/products.db", help="Database path")
    parser.add_argument("--output", default="scenarios.json", help="Output file path")
    parser.add_argument("--correct", type=int, default=30, help="Number of correct scenarios")
    parser.add_argument("--incorrect", type=int, default=20, help="Number of incorrect scenarios")
    parser.add_argument("--malicious", type=int, default=15, help="Number of malicious scenarios")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    db = DatabaseConnection(args.db_path)
    generator = ScenarioGenerator(db)
    
    scenarios = generator.generate_scenarios(
        num_correct=args.correct,
        num_incorrect=args.incorrect,
        num_malicious=args.malicious,
        random_seed=args.seed
    )
    
    generator.save_scenarios(scenarios, args.output)
    
    print(f"Generated {len(scenarios.scenarios)} test scenarios:")
    print(f"  - Correct: {args.correct}")
    print(f"  - Incorrect: {args.incorrect}")
    print(f"  - Malicious: {args.malicious}")
    print(f"Saved to: {args.output}")
    
    return 0


if __name__ == "__main__":
    exit(main())