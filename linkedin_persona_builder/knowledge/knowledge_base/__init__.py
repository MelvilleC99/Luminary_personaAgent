    def get_follow_up_strategy(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get follow-up strategy template"""
        try:
            data = self.load_examples()
            return data.get("follow_up_strategies", {}).get(strategy_name)
        except Exception as e:
            logger.error(f"Failed to get follow-up strategy: {e}")
            return None
    
    def get_clarification_example(self, criterion_name: str) -> Optional[Dict[str, Any]]:
        """Get clarification example for criterion"""
        try:
            data = self.load_examples()
            return data.get("clarification_examples", {}).get(criterion_name)
        except Exception as e:
            logger.error(f"Failed to get clarification example: {e}")
            return None


class ArchetypesLoader:
    """Load brand archetypes and communication styles"""
    
    def __init__(self):
        self.archetypes_path = os.path.join(
            os.path.dirname(__file__),
            "archetypes.yaml"
        )
        self.archetypes_data = None
    
    def load_archetypes(self) -> Dict[str, Any]:
        """Load archetypes from YAML file"""
        if self.archetypes_data is None:
            try:
                with open(self.archetypes_path, 'r', encoding='utf-8') as file:
                    self.archetypes_data = yaml.safe_load(file)
                logger.info("Archetypes loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load archetypes: {e}")
                self.archetypes_data = {}
        
        return self.archetypes_data
    
    def get_archetype(self, archetype_name: str) -> Optional[Dict[str, Any]]:
        """Get specific archetype data"""
        try:
            data = self.load_archetypes()
            return data.get("archetypes", {}).get(archetype_name)
        except Exception as e:
            logger.error(f"Failed to get archetype: {e}")
            return None
    
    def get_communication_style(self, style_name: str) -> Optional[Dict[str, Any]]:
        """Get communication style data"""
        try:
            data = self.load_archetypes()
            return data.get("communication_styles", {}).get(style_name)
        except Exception as e:
            logger.error(f"Failed to get communication style: {e}")
            return None
    
    def list_archetypes(self) -> List[str]:
        """Get list of available archetypes"""
        try:
            data = self.load_archetypes()
            return list(data.get("archetypes", {}).keys())
        except Exception as e:
            logger.error(f"Failed to list archetypes: {e}")
            return []


# Global instances
examples_loader = ExamplesLoader()
archetypes_loader = ArchetypesLoader()
